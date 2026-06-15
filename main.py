import asyncio
import time

import cv2
import mediapipe as mp
from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth


TV_IP = "192.168.0.5"
DEBOUNCE_SECONDS = 1.0

GESTURE_TO_COMMAND = {
    "OPEN_PALM": "HOME",
    "FIST": "DPAD_CENTER",
    "THUMBS_UP": "VOLUME_UP",
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

    if not any(fingers_up) and not thumb_extended:
        return "FIST"

    return None


async def main() -> None:
    global remote

    remote = await connect_tv()

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    last_command = ""
    last_command_time = 0.0

    with mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Could not read frame from webcam.")
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]
                handedness = "Right"

                if results.multi_handedness:
                    handedness = results.multi_handedness[0].classification[0].label

                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                )

                gesture = detect_gesture(hand_landmarks.landmark, handedness)
                if gesture:
                    command = GESTURE_TO_COMMAND[gesture]
                    now = time.monotonic()

                    if command != last_command or now - last_command_time >= DEBOUNCE_SECONDS:
                        display_command = "SELECT" if command == "DPAD_CENTER" else command
                        print(f"Gesture: {gesture} -> {display_command}")
                        send_tv_command(command)
                        last_command = command
                        last_command_time = now

            cv2.imshow("Gesture TV Remote", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            await asyncio.sleep(0)

    cap.release()
    cv2.destroyAllWindows()

    if remote is not None:
        remote.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
