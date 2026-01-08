import base64
import json
import os
import re
import urllib.error
import urllib.request

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Float32MultiArray, String
from dotenv import find_dotenv, load_dotenv


class EstimationJudgeNode(Node):
    def __init__(self):
        super().__init__("estimation_judge")

        load_dotenv(find_dotenv(usecwd=True))

        # Integration: update these topic defaults to match perception/control wiring.
        self.declare_parameter("input_mode", "compressed")
        self.declare_parameter("image_topic", "/perception/image_path")
        self.declare_parameter("compressed_topic", "/perception/image/compressed")
        self.declare_parameter("output_topic", "/estimation/type_id")
        self.declare_parameter("expected_count", 4)
        self.declare_parameter("model_name", "gemini-3-pro")
        self.declare_parameter("api_key_env", "GEMINI_API_KEY")
        self.declare_parameter("request_timeout_sec", 20.0)
        self.declare_parameter("temperature", 0.0)
        self.declare_parameter("max_output_tokens", 1024)
        self.declare_parameter("log_response", False)
        # Integration: if control cannot handle -1, change to a safe fallback ID.
        self.declare_parameter("unknown_type_id", -1.0)

        self.input_mode = self.get_parameter("input_mode").get_parameter_value().string_value
        self.image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        self.compressed_topic = self.get_parameter("compressed_topic").get_parameter_value().string_value
        self.output_topic = self.get_parameter("output_topic").get_parameter_value().string_value
        self.expected_count = int(self.get_parameter("expected_count").get_parameter_value().integer_value)
        self.model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self.api_key_env = self.get_parameter("api_key_env").get_parameter_value().string_value
        self.request_timeout_sec = float(
            self.get_parameter("request_timeout_sec").get_parameter_value().double_value
        )
        self.temperature = float(self.get_parameter("temperature").get_parameter_value().double_value)
        self.max_output_tokens = int(
            self.get_parameter("max_output_tokens").get_parameter_value().integer_value
        )
        self.log_response = bool(self.get_parameter("log_response").get_parameter_value().bool_value)
        self.unknown_type_id = float(self.get_parameter("unknown_type_id").get_parameter_value().double_value)

        # Integration: keep this mapping aligned with control-side type IDs.
        self.allowed_labels = ["can", "plastic", "paper", "box"]
        self.label_to_id = {"can": 0.0, "plastic": 1.0, "paper": 2.0, "box": 3.0}

        self._publisher = self.create_publisher(Float32MultiArray, self.output_topic, 10)

        mode = (self.input_mode or "").strip().lower()
        if mode == "compressed":
            self._subscription = self.create_subscription(
                CompressedImage,
                self.compressed_topic,
                self._on_compressed_image,
                10,
            )
        else:
            if mode and mode != "path":
                self.get_logger().warn(
                    f"unknown input_mode '{self.input_mode}', defaulting to 'path'"
                )
            self._subscription = self.create_subscription(
                String,
                self.image_topic,
                self._on_image_path,
                10,
            )

        self.get_logger().info(
            f"EstimationJudgeNode input_mode={mode or 'path'}; "
            f"publishing types on {self.output_topic}"
        )

    def _on_image_path(self, msg: String) -> None:
        image_path = msg.data.strip()
        if not image_path:
            self.get_logger().warn("received empty image path")
            return

        type_ids = self._classify_from_path(image_path)
        out_msg = Float32MultiArray()
        out_msg.data = type_ids
        self._publisher.publish(out_msg)

    def _on_compressed_image(self, msg: CompressedImage) -> None:
        if not msg.data:
            self.get_logger().warn("received empty compressed image")
            return

        mime_type = self._guess_mime_from_format(msg.format)
        type_ids = self._classify_from_bytes(bytes(msg.data), mime_type)
        out_msg = Float32MultiArray()
        out_msg.data = type_ids
        self._publisher.publish(out_msg)

    def _classify_from_path(self, image_path: str) -> list[float]:
        if not os.path.exists(image_path):
            self.get_logger().warn(f"image path does not exist: {image_path}")
            return [self.unknown_type_id] * self.expected_count

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
        except OSError as exc:
            self.get_logger().warn(f"failed to read image: {exc}")
            return [self.unknown_type_id] * self.expected_count

        return self._classify_from_bytes(image_bytes, self._guess_mime_type(image_path))

    def _classify_from_bytes(self, image_bytes: bytes, mime_type: str) -> list[float]:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            self.get_logger().warn(
                f"missing API key in env {self.api_key_env}; publishing unknown types"
            )
            return [self.unknown_type_id] * self.expected_count

        # Integration: if perception provides ordering or IDs, align this prompt/output parsing.
        prompt = (
            "너는 재활용 분류를 하는 분류기야. "
            f"허용 라벨: {', '.join(self.allowed_labels)}. "
            f"반드시 길이가 {self.expected_count}인 JSON 배열만 반환해. "
            "설명이나 코드블록 없이 JSON만 출력해. "
            "출력은 반드시 [로 시작하고 ]로 끝나야 해. "
            "출력 예시: [\"plastic\"]. "
            "순서는 인식 좌표 목록 순서와 반드시 일치해야 해. "
            "배경/그림자는 무시하고 물체 자체만 보고 판단해. "
            "인쇄문자, 로고, 포장재는 내용물이 아니라 물체의 일부로 간주해. "
            "잔여 액체/내용물은 무시하고 용기 재질/형태로 분류해. "
            "사진에서 제품명이 보이면 그 정보를 분류에 활용해. "
            "예외 규칙: 'Maeil' 혹은 '바이오'가 보이면 라벨은 paper. "
            "겉모습만으로 재질이 불확실하면 'unknown'을 반환해."
        )

        try:
            response_text = self._call_gemini(api_key, prompt, image_bytes, mime_type)
        except Exception as exc:
            self.get_logger().warn(f"Gemini request failed: {exc}")
            return [self.unknown_type_id] * self.expected_count

        if self.log_response:
            preview = response_text.replace("\n", "\\n")
            self.get_logger().info(
                f"Gemini raw response ({len(response_text)} chars): {preview}"
            )

        labels = self._parse_labels(response_text)
        type_ids = self._labels_to_ids(labels)

        if len(type_ids) < self.expected_count:
            type_ids.extend([self.unknown_type_id] * (self.expected_count - len(type_ids)))
        if len(type_ids) > self.expected_count:
            type_ids = type_ids[: self.expected_count]

        return type_ids

    def _call_gemini(self, api_key: str, prompt: str, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": encoded}},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=self.request_timeout_sec) as resp:
            body = resp.read().decode("utf-8")

        data = json.loads(body)
        candidates = data.get("candidates", [])
        if not candidates:
            if self.log_response:
                self.get_logger().info(f"Gemini raw body: {body}")
            raise RuntimeError("empty response from Gemini")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            if self.log_response:
                self.get_logger().info(f"Gemini raw body: {body}")
            raise RuntimeError("missing content parts in response")

        if self.log_response:
            finish_reason = candidates[0].get("finishReason")
            self.get_logger().info(
                f"Gemini finishReason={finish_reason}, parts={len(parts)}"
            )
            if finish_reason == "MAX_TOKENS":
                self.get_logger().warn(
                    "Gemini hit max tokens; consider increasing max_output_tokens"
                )

        texts = []
        for part in parts:
            if "text" in part:
                texts.append(part.get("text", ""))
        return "\n".join(texts)

    def _parse_labels(self, text: str) -> list[str]:
        cleaned = self._strip_code_fences(text).strip()
        parsed = None

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            bracketed = self._extract_bracketed_json(cleaned)
            if bracketed:
                try:
                    parsed = json.loads(bracketed)
                except json.JSONDecodeError:
                    parsed = None

        if isinstance(parsed, dict):
            parsed = parsed.get("labels")

        labels = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "label" in item:
                    labels.append(str(item["label"]))
                else:
                    labels.append(str(item))
        else:
            tokens = re.split(r"[,\n]+", cleaned)
            labels = [t.strip() for t in tokens if t.strip()]

        return labels

    def _guess_mime_type(self, image_path: str) -> str:
        # Integration: update this if perception uses other formats (e.g., png).
        lower = image_path.lower()
        if lower.endswith(".png"):
            return "image/png"
        return "image/jpeg"

    def _guess_mime_from_format(self, fmt: str) -> str:
        lower = (fmt or "").lower()
        if "png" in lower:
            return "image/png"
        if "jpg" in lower or "jpeg" in lower:
            return "image/jpeg"
        return "application/octet-stream"

    def _extract_bracketed_json(self, text: str) -> str | None:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        return text[start : end + 1]

    def _strip_code_fences(self, text: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return text

    def _labels_to_ids(self, labels: list[str]) -> list[float]:
        type_ids = []
        for label in labels:
            normalized = label.strip().lower()
            if normalized == "unknown":
                type_ids.append(self.unknown_type_id)
                continue

            matched = None
            for key in self.allowed_labels:
                if key in normalized:
                    matched = key
                    break

            if matched is None:
                type_ids.append(self.unknown_type_id)
            else:
                type_ids.append(self.label_to_id[matched])

        return type_ids


def main(args=None) -> None:
    rclpy.init(args=args)
    node = EstimationJudgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
