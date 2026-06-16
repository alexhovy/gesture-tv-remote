import asyncio
import time
import urllib.request

import cv2
import mediapipe as mp
from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe.tasks.python.vision.hand_landmarker import (
    HandLandmarker,
    HandLandmarkerOptions,
)
from mediapipe.tasks.python.vision.core.vision_task_running_mode import (
    VisionTaskRunningMode,
)


TV_IP = "192.168.0.5"
DEBOUNCE_SECONDS = 1.0
HOME_HOLD_SECONDS = 1.0
SWIPE_SECONDS = 0.45
SWIPE_DISTANCE = 0.22
MODEL_FILE = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

HAND_CONNECTIONS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
]

GESTURE_TO_COMMAND = {
    "OPEN_PALM": "HOME",
    "THUMBS_UP": "VOLUME_UP",
    "THUMBS_DOWN": "VOLUME_DOWN",
    "POINT": "BACK",
    "TWO_FINGERS": "MEDIA_PLAY_PAUSE",
    "SWIPE_LEFT": "DPAD_LEFT",
    "SWIPE_RIGHT": "DPAD_RIGHT",
    "SWIPE_UP": "DPAD_UP",
    "SWIPE_DOWN": "DPAD_DOWN",
    "OPEN_TO_FIST": "DPAD_CENTER",
}

remote: AndroidTVRemote | None = None


async def connect_tv() -> AndroidTVRemote | None:
    tv_remote = AndroidTVRemote(
        "Gesture TV Remote",
        "cert.pem",
        "key.pem",
        TV_IP,
        enable_voice=False,
    )

    if await tv_remote.async_generate_cert_if_missing():
        print("Generated cert.pem and key.pem")

    try:
        await tv_remote.async_connect()
    except InvalidAuth:
        print("TV needs pairing before commands can be sent.")
        print("Starting pairing. Enter the code shown on your TV.")
        try:
            await tv_remote.async_start_pairing()
            pairing_code = input("Pairing code: ").strip()
            await tv_remote.async_finish_pairing(pairing_code)
            await tv_remote.async_connect()
        except (CannotConnect, ConnectionClosed, InvalidAuth) as error:
            print(f"Pairing failed: {error}")
            return None
    except (CannotConnect, ConnectionClosed) as error:
        print(f"Could not connect to TV at {TV_IP}: {error}")
        return None

    print(f"Connected to TV at {TV_IP}")
    return tv_remote


def send_tv_command(command: str) -> None:
    if remote is None:
        print(f"TV not connected. Skipping command: {command}")
        return

    try:
        remote.send_key_command(command)
    except ConnectionClosed:
        print("TV connection closed. Command not sent.")
    except ValueError as error:
        print(f"Invalid TV command {command}: {error}")


def download_model_if_missing() -> None:
    try:
        open(MODEL_FILE, "rb").close()
    except FileNotFoundError:
        print(f"Downloading {MODEL_FILE}...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)


def draw_simple_landmarks(frame, landmarks) -> None:
    height, width = frame.shape[:2]

    for start, end in HAND_CONNECTIONS:
        start_point = (int(landmarks[start].x * width), int(landmarks[start].y * height))
        end_point = (int(landmarks[end].x * width), int(landmarks[end].y * height))
        cv2.line(frame, start_point, end_point, (0, 255, 0), 2)

    for landmark in landmarks:
        point = (int(landmark.x * width), int(landmark.y * height))
        cv2.circle(frame, point, 4, (0, 0, 255), -1)


def finger_is_extended(landmarks, tip_id: int, pip_id: int) -> bool:
    return landmarks[tip_id].y < landmarks[pip_id].y


def thumb_is_extended(landmarks, handedness: str) -> bool:
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]

    if handedness == "Left":
        return thumb_tip.x > thumb_ip.x
    return thumb_tip.x < thumb_ip.x


def thumb_is_up(landmarks) -> bool:
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_mcp = landmarks[2]

    y_distance = thumb_mcp.y - thumb_tip.y
    x_distance = abs(thumb_tip.x - thumb_mcp.x)

    return thumb_tip.y < thumb_ip.y < thumb_mcp.y and y_distance > x_distance


def thumb_is_down(landmarks) -> bool:
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_mcp = landmarks[2]

    y_distance = thumb_tip.y - thumb_mcp.y
    x_distance = abs(thumb_tip.x - thumb_mcp.x)

    return thumb_tip.y > thumb_ip.y > thumb_mcp.y and y_distance > x_distance


def hand_center(landmarks) -> tuple[float, float]:
    x = sum(landmark.x for landmark in landmarks) / len(landmarks)
    y = sum(landmark.y for landmark in landmarks) / len(landmarks)
    return x, y


def detect_swipe(position_history: list[tuple[float, float, float]]) -> str | None:
    if len(position_history) < 2:
        return None

    start_time, start_x, start_y = position_history[0]
    end_time, end_x, end_y = position_history[-1]
    if end_time - start_time > SWIPE_SECONDS:
        return None

    dx = end_x - start_x
    dy = end_y - start_y

    if abs(dx) > abs(dy) and abs(dx) >= SWIPE_DISTANCE:
        return "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"

    if abs(dy) > abs(dx) and abs(dy) >= SWIPE_DISTANCE:
        return "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"

    return None


def detect_gesture(landmarks, handedness: str) -> str | None:
    index_up = finger_is_extended(landmarks, 8, 6)
    middle_up = finger_is_extended(landmarks, 12, 10)
    ring_up = finger_is_extended(landmarks, 16, 14)
    pinky_up = finger_is_extended(landmarks, 20, 18)
    thumb_extended = thumb_is_extended(landmarks, handedness)

    fingers_up = [index_up, middle_up, ring_up, pinky_up]

    if all(fingers_up) and thumb_extended:
        return "OPEN_PALM"

    if not any(fingers_up) and thumb_is_up(landmarks):
        return "THUMBS_UP"

    if not any(fingers_up) and thumb_is_down(landmarks):
        return "THUMBS_DOWN"

    if index_up and middle_up and not ring_up and not pinky_up:
        return "TWO_FINGERS"

    if index_up and not middle_up and not ring_up and not pinky_up:
        return "POINT"

    if not any(fingers_up) and not thumb_extended:
        return "FIST"

    return None


def print_and_send_gesture(gesture: str) -> None:
    command = GESTURE_TO_COMMAND[gesture]
    display_command = command
    if command == "DPAD_CENTER":
        display_command = "SELECT"
    elif command == "MEDIA_PLAY_PAUSE":
        display_command = "PLAY_PAUSE"
    print(f"Gesture: {gesture} -> {display_command}")
    send_tv_command(command)


async def main() -> None:
    global remote

    remote = await connect_tv()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    last_command = ""
    last_command_time = 0.0
    previous_gesture = None
    open_palm_start_time = None
    position_history = []

    download_model_if_missing()
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_FILE),
        running_mode=VisionTaskRunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
    )
    hands = HandLandmarker.create_from_options(options)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read frame from webcam.")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            landmarks = None
            handedness = "Right"

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = hands.detect_for_video(mp_image, int(time.monotonic() * 1000))
            if results.hand_landmarks:
                landmarks = results.hand_landmarks[0]

                if results.handedness:
                    handedness = results.handedness[0][0].category_name

            if landmarks:
                draw_simple_landmarks(frame, landmarks)

                now = time.monotonic()
                center_x, center_y = hand_center(landmarks)
                position_history.append((now, center_x, center_y))
                position_history = [
                    item for item in position_history if now - item[0] <= SWIPE_SECONDS
                ]

                gesture = detect_gesture(landmarks, handedness)

                if gesture == "OPEN_PALM":
                    if open_palm_start_time is None:
                        open_palm_start_time = now
                else:
                    open_palm_start_time = None

                command_gesture = None
                swipe_gesture = detect_swipe(position_history)

                if swipe_gesture:
                    command_gesture = swipe_gesture
                    position_history = []
                elif previous_gesture == "OPEN_PALM" and gesture == "FIST":
                    command_gesture = "OPEN_TO_FIST"
                elif gesture == "OPEN_PALM":
                    if open_palm_start_time is not None and now - open_palm_start_time >= HOME_HOLD_SECONDS:
                        command_gesture = "OPEN_PALM"
                elif gesture in ("THUMBS_UP", "THUMBS_DOWN", "POINT", "TWO_FINGERS"):
                    command_gesture = gesture

                if command_gesture:
                    command = GESTURE_TO_COMMAND[command_gesture]

                    if command != last_command or now - last_command_time >= DEBOUNCE_SECONDS:
                        print_and_send_gesture(command_gesture)
                        last_command = command
                        last_command_time = now

                previous_gesture = gesture
            else:
                previous_gesture = None
                open_palm_start_time = None
                position_history = []

            cv2.imshow("Gesture TV Remote", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            await asyncio.sleep(0)
    finally:
        hands.close()

    cap.release()
    cv2.destroyAllWindows()

    if remote is not None:
        remote.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
