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
HOME_HOLD_SECONDS = 2.0
SWIPE_DISTANCE = 0.13
SWIPE_DOMINANCE = 1.15
BACK_PUSH_SECONDS = 0.8
BACK_PUSH_DISTANCE = 0.12
BACK_PUSH_MAX_DRIFT = 0.18
DEBUG_LOG_SECONDS = 0.5
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
    "PUSH_BACK": "BACK",
    "TWO_FINGERS": "MEDIA_PLAY_PAUSE",
    "SWIPE_LEFT": "DPAD_LEFT",
    "SWIPE_RIGHT": "DPAD_RIGHT",
    "SWIPE_UP": "DPAD_UP",
    "SWIPE_DOWN": "DPAD_DOWN",
    "OPEN_TO_FIST": "DPAD_CENTER",
}

remote: AndroidTVRemote | None = None
REPEATABLE_COMMANDS = {
    "DPAD_LEFT",
    "DPAD_RIGHT",
    "DPAD_UP",
    "DPAD_DOWN",
}


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


def index_is_pointing(landmarks) -> bool:
    index_tip = landmarks[8]
    index_pip = landmarks[6]
    index_mcp = landmarks[5]

    y_distance = index_mcp.y - index_tip.y
    x_distance = abs(index_tip.x - index_mcp.x)

    return index_tip.y < index_pip.y < index_mcp.y and y_distance > 1.6 * x_distance and y_distance > 0.12


def hand_center(landmarks) -> tuple[float, float, float]:
    x = sum(landmark.x for landmark in landmarks) / len(landmarks)
    y = sum(landmark.y for landmark in landmarks) / len(landmarks)
    size = max(
        max(landmark.x for landmark in landmarks) - min(landmark.x for landmark in landmarks),
        max(landmark.y for landmark in landmarks) - min(landmark.y for landmark in landmarks),
    )
    return x, y, size


def detect_swipe(start: tuple[float, float], end: tuple[float, float]) -> str | None:
    start_x, start_y = start
    end_x, end_y = end

    dx = end_x - start_x
    dy = end_y - start_y

    if abs(dx) < SWIPE_DISTANCE and abs(dy) < SWIPE_DISTANCE:
        return None

    if abs(dx) >= SWIPE_DISTANCE and abs(dx) >= SWIPE_DOMINANCE * abs(dy):
        return "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"

    if abs(dy) >= SWIPE_DISTANCE and abs(dy) >= SWIPE_DOMINANCE * abs(dx):
        return "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"

    return None


def detect_push_back(motion_history: list[tuple[float, float, float, float]]) -> str | None:
    if len(motion_history) < 2:
        return None

    start_time, start_x, start_y, start_size = motion_history[0]
    end_time, end_x, end_y, end_size = motion_history[-1]
    if end_time - start_time > BACK_PUSH_SECONDS:
        return None

    size_change = start_size - end_size
    drift = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5

    if size_change >= BACK_PUSH_DISTANCE and drift <= BACK_PUSH_MAX_DRIFT:
        return "PUSH_BACK"

    return None


def detect_gesture(landmarks, handedness: str) -> str | None:
    index_up = finger_is_extended(landmarks, 8, 6)
    middle_up = finger_is_extended(landmarks, 12, 10)
    ring_up = finger_is_extended(landmarks, 16, 14)
    pinky_up = finger_is_extended(landmarks, 20, 18)
    thumb_extended = thumb_is_extended(landmarks, handedness)

    fingers_up = [index_up, middle_up, ring_up, pinky_up]

    if all(fingers_up):
        return "OPEN_PALM"

    if index_up and middle_up and not ring_up and not pinky_up and not thumb_extended:
        return "TWO_FINGERS"

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


def log_debug(message: str) -> None:
    print(f"[DEBUG] {message}")


def get_detected_hands(results) -> list[tuple[list, str]]:
    detected_hands = []
    handedness_results = results.handedness or []

    for index, landmarks in enumerate(results.hand_landmarks or []):
        handedness = "Right"
        if index < len(handedness_results) and handedness_results[index]:
            handedness = handedness_results[index][0].category_name
        detected_hands.append((landmarks, handedness))

    return detected_hands


async def main() -> None:
    global remote

    remote = await connect_tv()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    last_command = ""
    last_command_time = 0.0
    last_command_gesture = None
    previous_gesture = None
    open_palm_start_time = None
    fist_start_position = None
    fist_last_position = None
    fist_started_from_open = False
    push_back_history = []
    last_debug_time = 0.0
    last_debug_message = ""

    download_model_if_missing()
    options = HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_FILE),
        running_mode=VisionTaskRunningMode.VIDEO,
        num_hands=2,
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

            now = time.monotonic()
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = hands.detect_for_video(mp_image, int(time.monotonic() * 1000))
            detected_hands = get_detected_hands(results)

            for landmarks, _ in detected_hands:
                draw_simple_landmarks(frame, landmarks)

            hand_gestures = [
                (landmarks, detect_gesture(landmarks, handedness))
                for landmarks, handedness in detected_hands
            ]
            activation_index = next(
                (
                    index
                    for index, (_, gesture) in enumerate(hand_gestures)
                    if gesture == "OPEN_PALM"
                ),
                None,
            )
            control_hand = next(
                (
                    item
                    for index, item in enumerate(hand_gestures)
                    if index != activation_index
                ),
                None,
            )

            debug_gestures = [
                gesture or "UNKNOWN" for _, gesture in hand_gestures
            ]

            if activation_index is not None and control_hand is not None:
                control_landmarks, gesture = control_hand
                center_x, center_y, hand_size = hand_center(control_landmarks)
                released_fist_select = False
                swipe_gesture = None

                if gesture == "OPEN_PALM":
                    if open_palm_start_time is None:
                        open_palm_start_time = now
                    if previous_gesture == "FIST" and fist_start_position and fist_last_position:
                        released_fist_select = fist_started_from_open
                    fist_start_position = None
                    fist_last_position = None
                    fist_started_from_open = False
                    push_back_history.append((now, center_x, center_y, hand_size))
                    push_back_history = [
                        item for item in push_back_history if now - item[0] <= BACK_PUSH_SECONDS
                    ]
                elif gesture == "FIST":
                    open_palm_start_time = None
                    push_back_history = []
                    if previous_gesture != "FIST" or fist_start_position is None:
                        fist_start_position = (center_x, center_y)
                        fist_started_from_open = previous_gesture == "OPEN_PALM"
                    fist_last_position = (center_x, center_y)
                    swipe_gesture = detect_swipe(fist_start_position, fist_last_position)
                else:
                    if previous_gesture == "FIST" and fist_start_position and fist_last_position:
                        released_fist_select = fist_started_from_open
                    open_palm_start_time = None
                    fist_start_position = None
                    fist_last_position = None
                    fist_started_from_open = False
                    push_back_history = []

                command_gesture = None
                push_back_gesture = detect_push_back(push_back_history)

                if push_back_gesture:
                    command_gesture = push_back_gesture
                    push_back_history = []
                elif swipe_gesture:
                    command_gesture = swipe_gesture
                    fist_started_from_open = False
                elif released_fist_select:
                    command_gesture = "OPEN_TO_FIST"
                elif gesture == "OPEN_PALM":
                    if open_palm_start_time is not None and now - open_palm_start_time >= HOME_HOLD_SECONDS:
                        command_gesture = "OPEN_PALM"
                elif gesture == "TWO_FINGERS":
                    command_gesture = gesture

                if command_gesture:
                    command = GESTURE_TO_COMMAND[command_gesture]

                    can_repeat = command in REPEATABLE_COMMANDS
                    gesture_changed = command_gesture != last_command_gesture
                    debounce_elapsed = now - last_command_time >= DEBOUNCE_SECONDS

                    if gesture_changed or (can_repeat and debounce_elapsed):
                        log_debug(f"sending command_gesture={command_gesture} command={command}")
                        print_and_send_gesture(command_gesture)
                        last_command = command
                        last_command_time = now
                        last_command_gesture = command_gesture
                else:
                    last_command_gesture = None

                previous_gesture = gesture
                debug_message = (
                    f"hands={len(detected_hands)} activated=True "
                    f"gestures={debug_gestures} control={gesture or 'UNKNOWN'} "
                    f"swipe={swipe_gesture or 'none'} push_back={push_back_gesture or 'none'} "
                    f"size={hand_size:.2f} command={command_gesture or 'none'}"
                )
            else:
                previous_gesture = None
                last_command_gesture = None
                open_palm_start_time = None
                fist_start_position = None
                fist_last_position = None
                fist_started_from_open = False
                push_back_history = []
                debug_message = (
                    f"hands={len(detected_hands)} activated=False "
                    f"gestures={debug_gestures} need_one_open_hand_and_one_control_hand"
                )

            if debug_message != last_debug_message or now - last_debug_time >= DEBUG_LOG_SECONDS:
                log_debug(debug_message)
                last_debug_message = debug_message
                last_debug_time = now

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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting.")
