import asyncio
import contextlib
import math
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
HOME_CHORD_SECONDS = 0.35
POINTER_DISTANCE = 0.08
POINTER_DOMINANCE = 1.15
VOLUME_DISTANCE = 0.16
PINCH_DISTANCE_RATIO = 0.22
VOICE_CAPTURE_SECONDS = 5.0
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
    "HOME": "HOME",
    "VOLUME_UP": "VOLUME_UP",
    "VOLUME_DOWN": "VOLUME_DOWN",
    "BACK": "BACK",
    "POINT_LEFT": "DPAD_LEFT",
    "POINT_RIGHT": "DPAD_RIGHT",
    "POINT_UP": "DPAD_UP",
    "POINT_DOWN": "DPAD_DOWN",
    "OPEN_TO_FIST": "DPAD_CENTER",
}

remote: AndroidTVRemote | None = None
REPEATABLE_COMMANDS = {
    "DPAD_LEFT",
    "DPAD_RIGHT",
    "DPAD_UP",
    "DPAD_DOWN",
    "VOLUME_UP",
    "VOLUME_DOWN",
}


async def connect_tv() -> AndroidTVRemote | None:
    tv_remote = AndroidTVRemote(
        "Gesture TV Remote",
        "cert.pem",
        "key.pem",
        TV_IP,
        enable_voice=True,
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


def hand_center(landmarks) -> tuple[float, float, float]:
    x = sum(landmark.x for landmark in landmarks) / len(landmarks)
    y = sum(landmark.y for landmark in landmarks) / len(landmarks)
    size = max(
        max(landmark.x for landmark in landmarks) - min(landmark.x for landmark in landmarks),
        max(landmark.y for landmark in landmarks) - min(landmark.y for landmark in landmarks),
    )
    return x, y, size


def landmark_distance(landmarks, first_id: int, second_id: int) -> float:
    first = landmarks[first_id]
    second = landmarks[second_id]
    return math.hypot(first.x - second.x, first.y - second.y)


def landmark_position(landmarks, landmark_id: int) -> tuple[float, float]:
    landmark = landmarks[landmark_id]
    return landmark.x, landmark.y


def detect_direction(
    start: tuple[float, float] | None,
    end: tuple[float, float],
    distance: float,
    dominance: float,
    prefix: str,
) -> str | None:
    if start is None:
        return None

    start_x, start_y = start
    end_x, end_y = end

    dx = end_x - start_x
    dy = end_y - start_y

    if abs(dx) < distance and abs(dy) < distance:
        return None

    if abs(dx) >= distance and abs(dx) >= dominance * abs(dy):
        return f"{prefix}_RIGHT" if dx > 0 else f"{prefix}_LEFT"

    if abs(dy) >= distance and abs(dy) >= dominance * abs(dx):
        return f"{prefix}_DOWN" if dy > 0 else f"{prefix}_UP"

    return None


def detect_volume(start_y: float | None, current_y: float) -> str | None:
    if start_y is None:
        return None

    dy = current_y - start_y

    if dy <= -VOLUME_DISTANCE:
        return "VOLUME_UP"

    if dy >= VOLUME_DISTANCE:
        return "VOLUME_DOWN"

    return None


def detect_gesture(landmarks, handedness: str) -> str | None:
    _, _, size = hand_center(landmarks)
    index_up = finger_is_extended(landmarks, 8, 6)
    middle_up = finger_is_extended(landmarks, 12, 10)
    ring_up = finger_is_extended(landmarks, 16, 14)
    pinky_up = finger_is_extended(landmarks, 20, 18)
    thumb_extended = thumb_is_extended(landmarks, handedness)
    pinch_distance = landmark_distance(landmarks, 4, 8)

    fingers_up = [index_up, middle_up, ring_up, pinky_up]

    if all(fingers_up):
        return "OPEN_PALM"

    if size > 0 and pinch_distance <= PINCH_DISTANCE_RATIO * size:
        return "PINCH"

    if index_up and middle_up and not ring_up and not pinky_up and not thumb_extended:
        return "TWO_FINGERS"

    if index_up and not middle_up and not ring_up and not pinky_up:
        return "POINT"

    if not any(fingers_up) and not thumb_extended:
        return "FIST"

    return None


def nearest_hand_index(
    hands: list[dict],
    target_position: tuple[float, float] | None,
) -> int | None:
    if not hands or target_position is None:
        return None

    target_x, target_y = target_position
    return min(
        range(len(hands)),
        key=lambda index: math.hypot(
            hands[index]["center"][0] - target_x,
            hands[index]["center"][1] - target_y,
        ),
    )


async def start_voice_capture() -> None:
    if remote is None:
        print("TV not connected. Skipping microphone capture.")
        return

    try:
        import sounddevice as sd
    except (ImportError, OSError) as error:
        print(f"Microphone capture unavailable: {error}")
        print("Install sounddevice and PortAudio support for microphone capture.")
        return

    voice_stream = None
    try:
        voice_stream = await remote.start_voice()
        loop = asyncio.get_running_loop()
        chunks: asyncio.Queue[bytes] = asyncio.Queue()

        def audio_callback(indata, frames, time_info, status) -> None:
            if status:
                loop.call_soon_threadsafe(log_debug, f"microphone status={status}")
            loop.call_soon_threadsafe(chunks.put_nowait, bytes(indata))

        print("Microphone: listening...")
        with sd.RawInputStream(
            samplerate=8000,
            channels=1,
            dtype="int16",
            blocksize=4096,
            callback=audio_callback,
        ):
            deadline = time.monotonic() + VOICE_CAPTURE_SECONDS
            while time.monotonic() < deadline:
                timeout = max(0.0, deadline - time.monotonic())
                try:
                    chunk = await asyncio.wait_for(chunks.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                voice_stream.send_chunk(chunk)
        print("Microphone: finished.")
    except asyncio.TimeoutError:
        print("TV did not start a voice session.")
    except ConnectionClosed:
        print("TV connection closed. Microphone capture stopped.")
    except Exception as error:
        print(f"Microphone capture failed: {error}")
    finally:
        if voice_stream is not None:
            voice_stream.end()


def print_and_send_gesture(gesture: str) -> None:
    command = GESTURE_TO_COMMAND[gesture]
    display_command = command
    if command == "DPAD_CENTER":
        display_command = "SELECT"
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
    primary_position = None
    primary_previous_gesture = None
    secondary_previous_gesture = None
    primary_close_time = None
    secondary_close_time = None
    primary_select_pending = False
    secondary_back_pending = False
    volume_start_y = None
    pointer_start_position = None
    voice_task = None
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

            hand_states = []
            for landmarks, handedness in detected_hands:
                center_x, center_y, hand_size = hand_center(landmarks)
                hand_states.append(
                    {
                        "landmarks": landmarks,
                        "gesture": detect_gesture(landmarks, handedness),
                        "center": (center_x, center_y),
                        "size": hand_size,
                    }
                )

            if primary_position is None:
                primary_index = next(
                    (
                        index
                        for index, hand in enumerate(hand_states)
                        if hand["gesture"] == "OPEN_PALM"
                    ),
                    None,
                )
            else:
                primary_index = nearest_hand_index(hand_states, primary_position)

            primary_hand = hand_states[primary_index] if primary_index is not None else None
            secondary_hand = next(
                (
                    hand
                    for index, hand in enumerate(hand_states)
                    if index != primary_index
                ),
                None,
            )

            debug_gestures = [
                hand["gesture"] or "UNKNOWN" for hand in hand_states
            ]

            if primary_hand is not None:
                primary_gesture = primary_hand["gesture"]
                primary_position = primary_hand["center"]
                secondary_gesture = secondary_hand["gesture"] if secondary_hand else None
                secondary_center = secondary_hand["center"] if secondary_hand else None
                secondary_landmarks = secondary_hand["landmarks"] if secondary_hand else None
                secondary_size = secondary_hand["size"] if secondary_hand else 0.0

                primary_closed = (
                    primary_previous_gesture == "OPEN_PALM" and primary_gesture == "FIST"
                )
                secondary_closed = (
                    secondary_previous_gesture == "OPEN_PALM" and secondary_gesture == "FIST"
                )

                if primary_closed:
                    primary_close_time = now
                    primary_select_pending = True

                if secondary_closed:
                    secondary_close_time = now
                    secondary_back_pending = True

                command_gesture = None
                volume_gesture = None
                pointer_gesture = None
                mic_gesture = None

                both_closed = (
                    primary_close_time is not None
                    and secondary_close_time is not None
                    and abs(primary_close_time - secondary_close_time) <= HOME_CHORD_SECONDS
                )
                if both_closed:
                    command_gesture = "HOME"
                    primary_close_time = None
                    secondary_close_time = None
                    primary_select_pending = False
                    secondary_back_pending = False
                    volume_start_y = None
                    pointer_start_position = None
                elif primary_select_pending and primary_close_time is not None:
                    if now - primary_close_time > HOME_CHORD_SECONDS:
                        command_gesture = "OPEN_TO_FIST"
                        primary_select_pending = False
                        primary_close_time = None
                elif secondary_back_pending and secondary_close_time is not None:
                    if now - secondary_close_time > HOME_CHORD_SECONDS:
                        command_gesture = "BACK"
                        secondary_back_pending = False
                        secondary_close_time = None

                if command_gesture is None and secondary_hand is not None:
                    if secondary_gesture == "PINCH":
                        pointer_start_position = None
                        if volume_start_y is None:
                            volume_start_y = secondary_center[1]
                        volume_gesture = detect_volume(volume_start_y, secondary_center[1])
                        command_gesture = volume_gesture
                    else:
                        volume_start_y = None

                    if command_gesture is None and secondary_gesture == "POINT":
                        pointer_position = landmark_position(secondary_landmarks, 8)
                        if pointer_start_position is None:
                            pointer_start_position = pointer_position
                        pointer_gesture = detect_direction(
                            pointer_start_position,
                            pointer_position,
                            POINTER_DISTANCE,
                            POINTER_DOMINANCE,
                            "POINT",
                        )
                        command_gesture = pointer_gesture
                    elif secondary_gesture != "POINT":
                        pointer_start_position = None

                    if command_gesture is None and secondary_gesture == "TWO_FINGERS":
                        mic_gesture = "MIC"
                        command_gesture = mic_gesture
                    elif secondary_gesture != "TWO_FINGERS":
                        mic_gesture = None

                if command_gesture:
                    command = GESTURE_TO_COMMAND.get(command_gesture)
                    can_repeat = command in REPEATABLE_COMMANDS if command else False
                    gesture_changed = command_gesture != last_command_gesture
                    debounce_elapsed = now - last_command_time >= DEBOUNCE_SECONDS

                    if gesture_changed or (can_repeat and debounce_elapsed):
                        if command_gesture == "MIC":
                            if voice_task is None or voice_task.done():
                                log_debug("starting microphone capture")
                                voice_task = asyncio.create_task(start_voice_capture())
                            else:
                                log_debug("microphone capture already running")
                        elif command:
                            log_debug(f"sending command_gesture={command_gesture} command={command}")
                            print_and_send_gesture(command_gesture)
                            last_command = command
                        last_command_time = now
                        last_command_gesture = command_gesture
                else:
                    last_command_gesture = None

                primary_previous_gesture = primary_gesture
                secondary_previous_gesture = secondary_gesture
                debug_message = (
                    f"hands={len(detected_hands)} activated=True "
                    f"gestures={debug_gestures} "
                    f"primary={primary_gesture or 'UNKNOWN'} "
                    f"secondary={secondary_gesture or 'none'} "
                    f"volume={volume_gesture or 'none'} "
                    f"pointer={pointer_gesture or 'none'} "
                    f"mic={mic_gesture or 'none'} "
                    f"size={secondary_size:.2f} command={command_gesture or 'none'}"
                )
            else:
                primary_position = None
                primary_previous_gesture = None
                secondary_previous_gesture = None
                last_command_gesture = None
                primary_close_time = None
                secondary_close_time = None
                primary_select_pending = False
                secondary_back_pending = False
                volume_start_y = None
                pointer_start_position = None
                debug_message = (
                    f"hands={len(detected_hands)} activated=False "
                    f"gestures={debug_gestures} need_primary_open_palm"
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
        if voice_task is not None and not voice_task.done():
            voice_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await voice_task
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
