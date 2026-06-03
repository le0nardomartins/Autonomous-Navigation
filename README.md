# AutoCar — SimplifyDetectors

Sistema de visão computacional para veículos autônomos que combina **detecção de faixas** (OpenCV + PID), **detecção de sinais de trânsito** (YOLOv11) e **detecção de obstáculos/pedestres** (YOLOv11n COCO) com uma máquina de estados para tomada de decisão autônoma.

---

## Funcionalidades

| Módulo | Descrição |
|---|---|
| Detector de faixas | Transformação bird-eye, threshold adaptável, erro lateral → PID dual |
| Detector de sinais | YOLOv11 — 15 classes (semáforos, STOP, limites de velocidade) |
| Detector de obstáculos | YOLOv11n COCO — pessoa, carro, caminhão, ônibus, bicicleta, moto |
| Sensor de proximidade | Estimativa de distância por área de bounding box (sensor virtual) |
| Máquina de estados | LIVRE → STOP → LIVRE / LIVRE → OBSTACULO → LIVRE |
| Modo vídeo | Loop em tempo real com trackbars de ROI e PID |
| Modo imagem | Visualização interativa com sliders e salvamento de configuração |

## Como usar

### Alternar modo

No topo de `detector_pista.py`:

```python
MODE       = "video"        # "video" | "image"
IMAGE_NAME = "image_1.png"  # arquivo em images/  (só para modo image)
```

### Modo vídeo

```bash
python detector_pista.py
```

- Janela **Comandos** — ajuste de ROI, limiar, velocidade e PID via trackbars
- Janela **Visao** — frame anotado com bird-eye, painel de telemetria e estado
- Arraste `Salvar Pipeline` para 1 para exportar as 6 etapas de processamento
- Tecla `Q` para sair

### Modo imagem

```bash
python detector_pista.py
```

- Janela **Controles** — sliders para ajustar a ROI em tempo real:

| Slider | Função |
|---|---|
| Linha superior | Largura da ROI no topo |
| Linha inferior | Largura da ROI na base |
| Altura sup | Posição Y do topo da ROI |
| Altura inf | Posição Y da base da ROI |
| Desl. X | Deslocamento horizontal do centro da ROI |
| Limiar | Threshold de binarização |

| Tecla | Ação |
|---|---|
| `S` | Salva configuração em `output/config.json` + exporta imagem |
| `P` | Salva as 6 etapas do pipeline em `output/` |
| `Q` / `ESC` | Sair |

A configuração salva é carregada automaticamente na próxima execução.

---

## Máquina de estados

| Estado | Gatilho | Efeito |
|---|---|---|
| `LIVRE` | — | PID normal, velocidade completa |
| `STOP` | Placa STOP ou semáforo vermelho/amarelo | Velocidade = 0, aguarda ~3 s |
| `OBSTACULO` | Bbox de obstáculo > 4 % do frame | Velocidade ÷ 2, desvio lateral de 60 px |

---

## Dashboard

O painel inferior exibe em tempo real:

- **Estado atual** (LIVRE / STOP / OBSTACULO) com cor indicativa
- Erro lateral, ângulo do servo, velocidade efetiva
- Ganhos PID (reta e curva)
- Flags de sinais: STOP · SG · SV
- Obstáculos detectados e barra de proximidade

---

## Classes detectadas

**Sinais** (`traffic_sign_detector.pt`):
Semáforo verde · vermelho · amarelo · Placa STOP · Velocidade 20/30/40/50/60/70/80/100/120 km/h

**Obstáculos** (`yolo11n.pt` COCO):
Pessoa · Bicicleta · Carro · Moto · Ônibus · Caminhão
