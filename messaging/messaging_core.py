import os
import json
import socket
import threading
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

_TWIN_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "AutoCar-DigitalTwin"))
_CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))

_lock = threading.Lock()

# ── Telemetria do veículo (Digital Twin) ─────────────────────────────────────
_state: dict = {
    "tabDashboard_rpm":      0,
    "tabDashboard_light":    False,
    "tabDashboard_rotate":   True,
    "tabDashboard_sensor_1": None,
    "tabDashboard_sensor_2": None,
    "tabDashboard_sensor_3": None,
    "tabDashboard_sensor_4": None,
    "tabDashboard_sensor_5": None,
}
_PWM_TO_RPM = 3.0

# ── Config do painel de controle ─────────────────────────────────────────────
_config: dict = {
    "ROI_Linha superior":          1280,
    "ROI_Linha inferior":          1280,
    "ROI_Altura sup":               263,
    "ROI_Altura inf":               541,
    "IMAGEM_Limiar":                195,
    "IMAGEM_Erro de transição":      12,
    "RETA_Kp":                      150,
    "RETA_Ki":                        0,
    "RETA_Kd":                        5,
    "CURVA_Kp":                     300,
    "CURVA_Ki":                       0,
    "CURVA_Kd":                       0,
    "PARÂMETROS DO CARRO_PWM":       30,
    "running":                    False,
}
_config_updated = False


def load_config_from_file() -> None:
    global _config
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        with _lock:
            _config.update(data)
    except Exception:
        pass


def update_state(pwm: int, running: bool) -> None:
    with _lock:
        _state["tabDashboard_rpm"]   = round(pwm * _PWM_TO_RPM)
        _state["tabDashboard_light"] = running and pwm > 0


def pop_config_update() -> dict | None:
    """Retorna config se o painel web a atualizou, senão None. Limpa o flag."""
    global _config_updated
    with _lock:
        if _config_updated:
            _config_updated = False
            return dict(_config)
        return None


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ── CORS ─────────────────────────────────────────────────────────────────────
@app.after_request
def _add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# ── API: telemetria ───────────────────────────────────────────────────────────
@app.route("/api/dashboard")
def api_dashboard():
    with _lock:
        snapshot = dict(_state)
    return jsonify({"data": snapshot})


# ── API: painel de controle ───────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
def api_config_get():
    with _lock:
        snapshot = dict(_config)
    return jsonify(snapshot)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    global _config_updated
    data = request.get_json(force=True, silent=True) or {}
    with _lock:
        _config.update(data)
        _config_updated = True
    return jsonify({"ok": True})


# ── Painel de controle web ────────────────────────────────────────────────────
@app.route("/panel")
def panel_page():
    return _PANEL_HTML


# ── Digital Twin (arquivos estáticos) ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(_TWIN_DIR, "index.html")


@app.route("/<path:filename>")
def twin_static(filename):
    return send_from_directory(_TWIN_DIR, filename)


# ── HTML do painel web ────────────────────────────────────────────────────────
_PANEL_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoCar — Painel de Controle</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#1e1e2e;color:#cdd6f4;font-family:'Courier New',monospace;min-height:100vh}
header{background:#181825;padding:12px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #45475a;position:sticky;top:0;z-index:10}
header h1{font-size:15px;color:#cdd6f4;flex:1;letter-spacing:1px}
.back-btn{background:#89b4fa;color:#1e1e2e;border:none;padding:7px 14px;border-radius:6px;font-family:inherit;font-size:12px;font-weight:bold;cursor:pointer}
.back-btn:hover{opacity:.85}
.actions{display:flex;gap:8px;padding:14px 16px 0}
.btn{flex:1;padding:12px;border:none;border-radius:6px;font-family:inherit;font-size:13px;font-weight:bold;cursor:pointer;transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-start{background:#a6e3a1;color:#1e1e2e}
.btn-stop{background:#f38ba8;color:#1e1e2e}
.btn-save{background:#cba6f7;color:#1e1e2e}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:14px 16px}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
.section{background:#181825;border-radius:8px;padding:14px}
.section-title{color:#89b4fa;font-size:10px;font-weight:bold;letter-spacing:1.5px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #45475a}
.ctrl{margin-bottom:10px}
.ctrl:last-child{margin-bottom:0}
.ctrl-label{display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px;color:#cdd6f4}
.ctrl-label span{color:#89b4fa;font-weight:bold;min-width:36px;text-align:right}
input[type=range]{width:100%;accent-color:#89b4fa;cursor:pointer}
.status-bar{text-align:center;font-size:10px;color:#6c7086;padding:8px 0 16px;letter-spacing:.5px}
.running-indicator{display:inline-block;width:7px;height:7px;border-radius:50%;background:#45475a;margin-right:5px;vertical-align:middle;transition:background .3s}
.running-indicator.on{background:#a6e3a1;box-shadow:0 0 6px #a6e3a1}
</style>
</head>
<body>
<header>
  <h1>⚙ Painel de Controle</h1>
  <button class="back-btn" onclick="window.location.href='/'">← Digital Twin</button>
</header>

<div class="actions">
  <button class="btn btn-start" id="btnStart" onclick="setRunning(true)">▶ Iniciar</button>
  <button class="btn btn-stop"  id="btnStop"  onclick="setRunning(false)">■ Parar</button>
  <button class="btn btn-save"  onclick="saveConfig()">💾 Salvar</button>
</div>

<div class="grid" id="grid"></div>
<p class="status-bar" id="status"><span class="running-indicator" id="runDot"></span>Carregando...</p>

<script>
const SECTIONS = [
  {title:"ROI",controls:[
    {key:"ROI_Linha superior",label:"Linha superior",min:0,max:1280},
    {key:"ROI_Linha inferior",label:"Linha inferior",min:0,max:1280},
    {key:"ROI_Altura sup",    label:"Altura sup",    min:0,max:720},
    {key:"ROI_Altura inf",    label:"Altura inf",    min:0,max:720},
  ]},
  {title:"IMAGEM",controls:[
    {key:"IMAGEM_Limiar",             label:"Limiar",             min:0,max:255},
    {key:"IMAGEM_Erro de transição",label:"Erro de transição",min:0,max:100},
  ]},
  {title:"RETA — PID",controls:[
    {key:"RETA_Kp",label:"Kp",min:0,max:1000},
    {key:"RETA_Ki",label:"Ki",min:0,max:1000},
    {key:"RETA_Kd",label:"Kd",min:0,max:1000},
  ]},
  {title:"CURVA — PID",controls:[
    {key:"CURVA_Kp",label:"Kp",min:0,max:1000},
    {key:"CURVA_Ki",label:"Ki",min:0,max:1000},
    {key:"CURVA_Kd",label:"Kd",min:0,max:1000},
  ]},
  {title:"PARÂMETROS DO CARRO",controls:[
    {key:"PARÂMETROS DO CARRO_PWM",label:"PWM",min:0,max:255},
  ]},
];

let debounceTimer=null, pendingUpdate={}, currentConfig={};

function buildUI(cfg){
  currentConfig=cfg;
  const grid=document.getElementById('grid');
  grid.innerHTML='';
  SECTIONS.forEach((sec,si)=>{
    const div=document.createElement('div');
    div.className='section';
    const title=document.createElement('div');
    title.className='section-title';
    title.textContent=sec.title;
    div.appendChild(title);
    sec.controls.forEach((ctrl,ci)=>{
      const id=`c${si}_${ci}`;
      const val=cfg[ctrl.key]??ctrl.min;
      const row=document.createElement('div');
      row.className='ctrl';
      row.dataset.key=ctrl.key;
      row.innerHTML=`
        <div class="ctrl-label"><label>${ctrl.label}</label><span id="${id}L">${val}</span></div>
        <input type="range" id="${id}I" min="${ctrl.min}" max="${ctrl.max}" value="${val}">`;
      div.appendChild(row);
      row.querySelector('input').addEventListener('input',function(){
        const v=parseInt(this.value);
        document.getElementById(id+'L').textContent=v;
        currentConfig[ctrl.key]=v;
        pendingUpdate[ctrl.key]=v;
        clearTimeout(debounceTimer);
        debounceTimer=setTimeout(flushUpdate,300);
      });
    });
    grid.appendChild(div);
  });
  updateRunIndicator(cfg.running);
}

function updateRunIndicator(running){
  const dot=document.getElementById('runDot');
  dot.className='running-indicator'+(running?' on':'');
}

function flushUpdate(){
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pendingUpdate)})
    .then(()=>{pendingUpdate={};setStatus('Salvo • '+new Date().toLocaleTimeString())})
    .catch(()=>setStatus('Erro ao salvar'));
}

function saveConfig(){
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...currentConfig,_save:true})})
    .then(()=>setStatus('Configuração salva'));
}

function setRunning(val){
  currentConfig.running=val;
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({running:val})})
    .then(()=>{updateRunIndicator(val);setStatus(val?'Iniciado':'Parado');});
}

function setStatus(msg){
  document.getElementById('status').innerHTML='<span class="running-indicator'+(currentConfig.running?' on':'')+'" id="runDot"></span>'+msg;
}

async function syncConfig(){
  try{
    const cfg=await fetch('/api/config').then(r=>r.json());
    document.querySelectorAll('.ctrl').forEach(row=>{
      const key=row.dataset.key;
      if(pendingUpdate[key]!==undefined)return;
      const inp=row.querySelector('input');
      const lbl=row.querySelector('span');
      if(inp&&cfg[key]!==undefined){inp.value=cfg[key];lbl.textContent=cfg[key];}
    });
    if(cfg.running!==undefined)updateRunIndicator(cfg.running);
  }catch{}
}

fetch('/api/config').then(r=>r.json()).then(cfg=>{buildUI(cfg);setStatus('Conectado');}).catch(()=>setStatus('Sem conexão'));
setInterval(syncConfig,2000);
</script>
</body>
</html>"""
