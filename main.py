import time
import threading
import json

import cv2
import numpy as np
import serial

from PID import PID
from CtrlPanel import ControlPanel
from imageProcess import laneDetectionPipeline, getFrameDimensions
from hud import drawDots, addInfo
from signDetector import SignDetector


def pidHub(erro, pid_straight, pid_curve, dt=0.2):
    if -panel.get("IMAGEM", "Erro de transição") < erro < panel.get("IMAGEM", "Erro de transição"):
        return pid_straight.update(erro, dt=dt)
    return pid_curve.update(erro, dt=dt)


def mainLoop():
    cv2.namedWindow("Visão", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Visão", 960, 700)

    ser = serial.Serial(COM, 9600, timeout=1)
    time.sleep(2)

    error = 0
    angle = 0
    last_send = 0
    last_rx   = "Stand by..."
    last_run  = None
    prev_flags = (False, False, False)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        img = frame.copy()

        # ── Detecção de sinais de trânsito ────────────────────
        sign_det.update(frame)
        flag_stop, flag_sg, flag_sv = sign_det.get_flags()

        # Log apenas quando o estado dos sinais muda
        curr_flags = (flag_stop, flag_sg, flag_sv)
        if curr_flags != prev_flags:
            if flag_stop:
                panel.log("[SINAL] Placa STOP — motores parados", "warn")
            elif flag_sv:
                panel.log("[SINAL] Semáforo VERMELHO — motores parados", "warn")
            elif flag_sg:
                panel.log("[SINAL] Semáforo VERDE — retomando", "ok")
            prev_flags = curr_flags

        # ── Leitura dos controles ─────────────────────────────
        upper        = panel.get("ROI", "Linha superior")
        lower        = panel.get("ROI", "Linha inferior")
        y_top        = panel.get("ROI", "Altura sup")
        y_bot        = panel.get("ROI", "Altura inf")
        limiar_value = panel.get("IMAGEM", "Limiar")
        pwm          = panel.get("PARÂMETROS DO CARRO", "PWM")

        kp_straight = panel.get("RETA", "Kp") / 100.0
        ki_straight = panel.get("RETA", "Ki") / 1000.0
        kd_straight = panel.get("RETA", "Kd") / 100.0
        pid_straight.setValues(kp_straight, ki_straight, kd_straight)

        kp_curve = panel.get("CURVA", "Kp") / 100.0
        ki_curve = panel.get("CURVA", "Ki") / 1000.0
        kd_curve = panel.get("CURVA", "Kd") / 100.0
        pid_curve.setValues(kp_curve, ki_curve, kd_curve)
        
        run = panel._IsRunning()

        # ── Definição dos pontos de perspectiva ─────────────────────────────
        cx = width // 2

        pts_origin = np.float32([
            [cx - upper // 2, y_top],
            [cx + upper // 2, y_top],
            [cx + lower // 2, y_bot],
            [cx - lower // 2, y_bot],
        ])

        pts_destiny = np.float32([
            [0,     0    ],
            [ROI_W, 0    ],
            [ROI_W, ROI_H],
            [0,     ROI_H],
        ])

        # ── Visualização dos pontos e ROI ─────────────────────────────
        pts_poly = pts_origin.astype(np.int32).reshape((-1, 1, 2))
        overlay  = img.copy()
        cv2.fillPoly(overlay, [pts_poly], color=(255, 0, 0))
        cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
        cv2.polylines(img, [pts_poly], isClosed=True, color=(255, 0, 0), thickness=2)
        drawDots(img, pts_origin, ["P1", "P2", "P3", "P4"])

        M   = cv2.getPerspectiveTransform(pts_origin, pts_destiny)
        roi = cv2.warpPerspective(frame, M, (ROI_W, ROI_H))

        # ── Processamento da ROI ─────────────────────────────
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, limiar = cv2.threshold(gray, limiar_value, 255, cv2.THRESH_BINARY)
        limiar_bgr = cv2.cvtColor(limiar, cv2.COLOR_GRAY2BGR)

        error, limiar_bgr, lane_state = laneDetectionPipeline(ROI_H, ROI_W, limiar, limiar_bgr, last_error=error)

        # ── Envio de dados para o Arduino ─────────────────────────────
        if run:
            now = time.time() * 1000
            if now - last_send >= 200:
                last_send = now
                angle = pidHub(error, pid_straight, pid_curve, dt=0.2)

                # STOP ou semáforo vermelho → zera PWM
                effective_pwm = 0 if (flag_stop or flag_sv) else pwm

                data = {
                    "DEVIATION": False,
                    "STOP":      flag_stop,
                    "SG":        flag_sg,
                    "SV":        flag_sv,
                    "SERVO":     int(angle + 90),
                    "PWM":       effective_pwm,
                }

                msg = json.dumps(data) + '\n'
                ser.write(msg.encode('utf-8'))
                panel.log(f"TX → {msg.strip()}", "tx")

        else:
            if last_run != False:  # só envia uma vez ao parar
                data = {
                    "DEVIATION": False,
                    "STOP":      True,
                    "SG":        False,
                    "SV":        False,
                    "SERVO":     int(angle + 90),
                    "PWM":       0,
                }
                msg = json.dumps(data) + '\n'
                ser.write(msg.encode('utf-8'))
                panel.log(f"TX → {msg.strip()}", "tx")
                panel.log("[CONTROLE MANUAL] veículo parado pelo painel de controle", "warn")

        last_run = run

        if ser.in_waiting:
            response = ser.readline().decode('utf-8', errors='ignore').strip()
            if response:
                last_rx = response  # ← atualiza a última mensagem recebida
                panel.log(f"RX ← {response}", "rx")

        # ── Dashboard ──────────────────────────────────────
        sign_det.draw(img)

        img_view  = cv2.resize(img, (960, 540))
        bird_view = cv2.resize(limiar_bgr, (320, 180))

        img_view[10:190, 630:950] = bird_view
        cv2.rectangle(img_view, (630, 10), (950, 190), (0, 255, 255), 2)
        cv2.putText(img_view, "Bird Eye", (635, 205),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        info = addInfo(error, angle, pwm, kp_straight, ki_straight, kd_straight,
                       kp_curve, ki_curve, kd_curve, last_rx, run,
                       flag_stop, flag_sg, flag_sv)

        dashboard = np.vstack((img_view, info))
        cv2.imshow("Visão", dashboard)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    ser.close()
    cv2.destroyAllWindows()

def _select_com() -> str:
    from serial.tools import list_ports
    ports = [p.device for p in list_ports.comports()]
    if not ports:
        com = input("[COM] Nenhuma porta detectada. Digite manualmente (ex: COM3): ").strip()
        return com or "COM5"
    if len(ports) == 1:
        print(f"[COM] Porta detectada automaticamente: {ports[0]}")
        return ports[0]
    print("[COM] Portas disponíveis:")
    for i, p in enumerate(ports):
        print(f"  [{i}] {p}")
    try:
        idx = int(input(f"[COM] Escolha o número (0-{len(ports)-1}): ").strip())
        return ports[idx]
    except (ValueError, IndexError):
        print(f"[COM] Entrada inválida, usando {ports[0]}")
        return ports[0]


def _open_camera() -> cv2.VideoCapture:
    for idx in (1, 0):
        c = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        c.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        c.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if c.isOpened() and c.read()[0]:
            print(f"[CAM] Camera aberta no indice {idx}")
            return c
        c.release()
    print("[ERRO] Nenhuma camera disponivel (indices 0 e 1 falharam).")
    exit()

cap = _open_camera()
ret, frame = cap.read()

if not ret:
    print("[ERRO] Falha ao ler o primeiro frame.")
    exit()

height, width = getFrameDimensions(frame, 1)

pid_straight  = PID(Kp=0, Ki=0, Kd=0, output_limit=90.0)
pid_curve = PID(Kp=0, Ki=0, Kd=0, output_limit=90.0)

ROI_W = 320
ROI_H = 240
COM = _select_com()

sign_det = SignDetector("model/traffic_sign_detector.pt")

panel = ControlPanel(width, height)
t = threading.Thread(target=mainLoop, daemon=True)
t.start()

panel.run()
