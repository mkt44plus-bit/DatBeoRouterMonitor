(() => {
  const API = "../cgi-bin/datbeo-traffic";
  const CAM_API = "../cgi-bin/datbeo-cameras";
  const app = document.getElementById("app");
  let key = localStorage.getItem("datbeo_api_key") || "";
  let routerLabel = location.host;
  let data = {traffic:[],leases:[],websites:[]};
  let cameras = [];
  let lastUpdated = "";
  let page = localStorage.getItem("datbeo_page") || "overview";
  let selectedMac = localStorage.getItem("datbeo_selected_mac") || null;
  let timer = null;
  let userInteracting = false;
  let previousTraffic = new Map();
  let speedByMac = new Map();
  let previousTrafficTime = 0;
  let hlsPlayers = {};

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  function saveUiState(){
    localStorage.setItem("datbeo_page",page);
    if(selectedMac) localStorage.setItem("datbeo_selected_mac",selectedMac);
    else localStorage.removeItem("datbeo_selected_mac");
    localStorage.setItem("datbeo_scroll_y",String(window.scrollY||0));
  }

  const esc = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const bytes = n => {n=Number(n)||0;const u=["B","KB","MB","GB","TB"];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++;}return i===0?Math.round(n)+" B":n.toFixed(1)+" "+u[i];};
  const speed = b => {const n=Math.max(0,Number(b)||0);if(n>=1000000)return(n/1000000).toFixed(1)+" Mbps";if(n>=1000)return(n/1000).toFixed(0)+" Kbps";return Math.round(n)+" bps";};
  const deviceName = m => {const x=data.leases.find(v=>String(v.mac||"").toLowerCase()===String(m||"").toLowerCase());return x?(x.name||"Thiết bị"):"Thiết bị";};
  const deviceIp = m => {const x=data.leases.find(v=>String(v.mac||"").toLowerCase()===String(m||"").toLowerCase());return x?(x.ip||""):"";};
  const icon = n => /iphone|android|phone|điện thoại/i.test(n)?"▣":/laptop|mac|pc|máy/i.test(n)?"▱":"◉";

  async function load(){
    const r=await fetch(API+"?key="+encodeURIComponent(key),{cache:"no-store"});
    const t=await r.text(); if(!r.ok)throw new Error("HTTP "+r.status);
    let j; try{j=JSON.parse(t);}catch(e){j=JSON.parse(t.trim().replace(/("traffic"\s*:\s*)\[\s*,\s*/,"$1["));}
    if(j.error)throw new Error(j.error);
    const next=Array.isArray(j.traffic)?j.traffic:[]; const now=Date.now();
    const dt=previousTrafficTime?Math.max(.5,(now-previousTrafficTime)/1000):0; const ns=new Map();
    next.forEach(x=>{const m=String(x.mac||"").toLowerCase(),o=previousTraffic.get(m),rx=Number(x.rx_bytes||0),tx=Number(x.tx_bytes||0);ns.set(m,o&&dt?{rxBps:Math.max(0,rx-o.rx)*8/dt,txBps:Math.max(0,tx-o.tx)*8/dt}:{rxBps:0,txBps:0});});
    previousTraffic=new Map(next.map(x=>[String(x.mac||"").toLowerCase(),{rx:Number(x.rx_bytes||0),tx:Number(x.tx_bytes||0)}]));
    previousTrafficTime=now; speedByMac=ns;
    data={traffic:next,leases:Array.isArray(j.leases)?j.leases:[],websites:Array.isArray(j.websites)?j.websites:[]};
    routerLabel=j.netbird_ip||location.host; lastUpdated=new Date().toLocaleTimeString("vi-VN",{hour12:false});
  }

  async function loadCameras(){
    const r=await fetch(CAM_API+"?action=list&key="+encodeURIComponent(key),{cache:"no-store"});
    const j=await r.json(); if(!r.ok||j.error==="unauthorized")throw new Error(j.error||("HTTP "+r.status));
    cameras=Array.isArray(j.cameras)?j.cameras:[];
  }

  async function cameraAction(p){
    const r=await fetch(CAM_API+"?key="+encodeURIComponent(key),{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams(p).toString()});
    const j=await r.json(); if(!r.ok||j.ok===false)throw new Error(j.error||("HTTP "+r.status)); return j;
  }
  async function cameraNetworkInfo(){
    const r=await fetch(CAM_API+"?action=lan_info&key="+encodeURIComponent(key),{cache:"no-store"});
    const j=await r.json(); if(!r.ok||j.ok===false)throw new Error(j.error||("HTTP "+r.status)); return j;
  }

  function nav(){return `<div class="glass nav"><button data-p="overview">⌂<br><span class="small">Tổng quan</span></button><button data-p="camera">▣<br><span class="small">Camera</span></button><button data-p="web">◎<br><span class="small">Website</span></button><button data-p="stats">▥<br><span class="small">Thống kê</span></button><button data-p="settings">⚙<br><span class="small">Cài đặt</span></button></div>`;}
  function bindNav(){document.querySelectorAll(".nav button").forEach(b=>b.onclick=()=>{page=b.dataset.p;saveUiState();render();setTimeout(()=>window.scrollTo(0,0),0);});}

  function renderLogin(msg=""){
    app.innerHTML=`<div class="shell"><div class="container"><div class="brand">HDB</div><div class="sub">OpenWrt Router • NetBird</div><div class="glass login"><input id="key" class="field" type="password" placeholder="API KEY" value="${esc(key)}"><button id="go" class="primary">Đăng nhập</button><div class="hint">Dashboard chạy trực tiếp từ router.</div><div class="status">${esc(msg)}</div></div></div></div>`;
    document.getElementById("go").onclick=async()=>{key=document.getElementById("key").value.trim();if(!key)return renderLogin("Nhập API KEY.");try{await load();await loadCameras();localStorage.setItem("datbeo_api_key",key);page="overview";selectedMac=null;saveUiState();render();}catch(e){renderLogin("Không kết nối được: "+e.message);}};
  }

  function cameraTiles(){
    const add=`<div class="glass camera-tile add-camera" id="add-camera"><div class="camera-plus">+</div><div>Thêm Camera</div></div>`;
    const items=cameras.map(c=>`<div class="glass camera-tile"><div class="camera-title">${esc(c.name)}</div><div class="camera-ip">${esc(c.ip)}:${esc(c.port||"554")}</div><div class="camera-video-wrap"><div class="camera-placeholder" id="cam-placeholder-${esc(c.id)}">Camera sẵn sàng</div><video id="cam-video-${esc(c.id)}" class="camera-video" controls muted playsinline></video></div><div class="camera-actions"><button class="camera-btn play" data-camera="${esc(c.id)}">▶ Xem trực tiếp</button><button class="camera-btn test" data-camera="${esc(c.id)}">Kiểm tra</button><button class="camera-btn danger" data-camera="${esc(c.id)}">Xóa</button></div></div>`).join("");
    return `<div class="camera-grid">${add}${items}</div>`;
  }

  function renderOverview(){
    const traffic=[...data.traffic].sort((a,b)=>(Number(b.rx_bytes)+Number(b.tx_bytes))-(Number(a.rx_bytes)+Number(a.tx_bytes)));
    const rx=traffic.reduce((s,x)=>s+Number(x.rx_bytes||0),0),tx=traffic.reduce((s,x)=>s+Number(x.tx_bytes||0),0);
    app.innerHTML=`<div class="shell"><div class="container"><div class="brand">HDB</div><div id="status" class="status">● Đang kết nối • ${esc(lastUpdated)}</div><div style="text-align:center"><span class="pill">◎ ${esc(routerLabel)}</span></div><div class="glass grid3"><div class="metric"><div class="icon">↓</div><div class="label">Tải xuống</div><div id="total-rx" class="value">${bytes(rx)}</div></div><div class="metric"><div class="icon">↑</div><div class="label">Tải lên</div><div id="total-tx" class="value">${bytes(tx)}</div></div><div class="metric"><div class="icon">●</div><div class="label">Thiết bị</div><div id="total-devices" class="value">${traffic.length}</div></div></div>
      <div class="section-head"><h2>Thiết bị</h2></div><div id="devices">${traffic.length?traffic.map(t=>`<div class="glass card device" data-mac="${esc(t.mac)}"><div class="iconbox">${icon(deviceName(t.mac))}</div><div><div class="name">${esc(deviceName(t.mac))}</div><div class="small">${esc(deviceIp(t.mac)||t.mac)}</div><div class="small online">● Online • ${Number(t.conns||0)} kết nối</div></div><div class="right"><div>↓ ${bytes(t.rx_bytes)}</div><div>↑ ${bytes(t.tx_bytes)}</div></div></div>`).join(""):"<div class=\"glass card error\">Chưa có dữ liệu traffic.</div>"}</div>
      <div class="section-head"><h2>Website đã truy cập</h2><span class="link" id="allweb">Xem tất cả ›</span></div><div id="overview-websites" class="glass card">${renderWebsiteRows(data.websites.slice(0,8))}</div>${nav()}</div></div>`;
    document.querySelectorAll("#devices .device").forEach(el=>el.onclick=()=>{selectedMac=el.dataset.mac;page="device";saveUiState();render();});
    document.getElementById("allweb").onclick=()=>{page="web";saveUiState();render();};
    bindNav();
  }

  function renderCamera(){
    app.innerHTML=`<div class="shell"><div class="container"><div class="section-head"><h2>Camera</h2><span class="small">${cameras.length} camera</span></div><div class="small camera-help">Thêm Camera → quét dải IP → chọn IP → nhập RTSP và thông tin đăng nhập.</div><div id="camera-section">${cameraTiles()}</div>${nav()}</div></div>`;
    document.getElementById("add-camera").onclick=()=>openCameraScanner();
    bindCameraButtons();bindNav();
  }

  function renderDevice(){
    const d=data.traffic.find(t=>String(t.mac||"").toLowerCase()===String(selectedMac||"").toLowerCase());
    if(!d){page="overview";selectedMac=null;saveUiState();return renderOverview();}
    const name=deviceName(d.mac),ip=deviceIp(d.mac),sp=speedByMac.get(String(d.mac).toLowerCase())||{rxBps:0,txBps:0};
    app.innerHTML=`<div class="shell"><div class="container"><div class="section-head"><h2>${esc(name)}</h2><span class="link" id="device-back">‹ Thiết bị</span></div><div class="glass card"><div class="tableline"><span>Tên</span><span class="domain">${esc(name)}</span></div><div class="tableline"><span>MAC</span><span class="domain">${esc(d.mac)}</span></div><div class="tableline"><span>IP</span><span class="domain">${esc(ip||"Chưa có")}</span></div></div><div class="glass card grid3"><div class="metric"><div class="label">Download</div><div id="device-rx-total" class="value">${bytes(d.rx_bytes)}</div></div><div class="metric"><div class="label">Upload</div><div id="device-tx-total" class="value">${bytes(d.tx_bytes)}</div></div><div class="metric"><div class="label">Kết nối</div><div id="device-conns" class="value">${Number(d.conns||0)}</div></div></div><div class="glass card grid3"><div class="metric"><div class="label">Tốc độ tải xuống</div><div id="device-rx-speed" class="value">${speed(sp.rxBps)}</div></div><div class="metric"><div class="label">Tốc độ tải lên</div><div id="device-tx-speed" class="value">${speed(sp.txBps)}</div></div><div class="metric"><div class="label">Trạng thái</div><div class="value online">Online</div></div></div><div class="section-head"><h2>Website</h2></div><div id="device-sites" class="glass card">${renderWebsiteRows(data.websites.filter(x=>x.ip===ip),50)}</div>${nav()}</div></div>`;
    document.getElementById("device-back").onclick=()=>{page="overview";selectedMac=null;saveUiState();render();};bindNav();
  }

  function renderWeb(){
    const ips=[...new Set(data.websites.map(x=>x.ip).filter(Boolean))],rows=selectedMac?data.websites:data.websites;
    app.innerHTML=`<div class="shell"><div class="container"><div class="section-head"><h2>Website</h2><span class="link" id="back">‹ Tổng quan</span></div><div class="glass card"><div class="small">Website gần đây</div></div><div class="glass card">${renderWebsiteRows(rows,200)}</div>${nav()}</div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";saveUiState();render();};bindNav();
  }

  function renderWebsiteRows(rows,limit=8){const shown=rows.slice(-limit).reverse();if(!shown.length)return "<div class=\"muted\">Chưa có dữ liệu DNS.</div>";return shown.map(x=>`<div class="tableline"><span>◎</span><span class="domain">${esc(x.domain)}</span><span class="small">${esc(x.time)}</span></div>`).join("");}

  function renderStats(){
    const top=[...data.traffic].sort((a,b)=>(Number(b.rx_bytes)+Number(b.tx_bytes))-(Number(a.rx_bytes)+Number(a.tx_bytes)));
    app.innerHTML=`<div class="shell"><div class="container"><div class="section-head"><h2>Thống kê</h2><span class="link" id="back">‹ Tổng quan</span></div><div class="glass card">${top.length?top.map(t=>`<div class="tableline"><span class="domain">${esc(deviceName(t.mac))}</span><span>↓ ${bytes(t.rx_bytes)} • ↑ ${bytes(t.tx_bytes)}</span></div>`).join(""):"Chưa có dữ liệu."}</div>${nav()}</div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";saveUiState();render();};bindNav();
  }

  function renderSettings(){
    app.innerHTML=`<div class="shell"><div class="container"><div class="section-head"><h2>Cài đặt</h2><span class="link" id="back">‹ Tổng quan</span></div><div class="glass card"><div class="small">Router</div><div class="name">${esc(location.host)}</div><button id="logout" class="primary">Xóa KEY và đăng xuất</button></div>${nav()}</div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";saveUiState();render();};
    document.getElementById("logout").onclick=()=>{localStorage.removeItem("datbeo_api_key");localStorage.removeItem("datbeo_page");localStorage.removeItem("datbeo_selected_mac");key="";page="overview";selectedMac=null;renderLogin();};bindNav();
  }

  function openCameraScanner(){
    document.body.insertAdjacentHTML("beforeend",`<div id="camera-scan-modal" class="modal-overlay"><div class="modal glass"><div class="section-head"><h2>Quét thiết bị trong router</h2><span id="close-camera-scan" class="link">✕</span></div><div class="small camera-help">Điện thoại đang truy cập router qua NetBird. Router sẽ quét mạng LAN phía sau nó để tìm các thiết bị đang hoạt động; thiết bị có RTSP sẽ hiện RTSP, thiết bị còn lại hiện HTTP.</div><div class="small" id="camera-lan-info">Đang lấy dải mạng của router...</div><div class="scan-row"><input id="camera-cidr" class="field" placeholder="Ví dụ 10.1.1.1/24" value=""><button id="camera-scan" class="primary scan-button">Quét</button></div><div id="camera-scan-result" class="scan-results"></div></div></div>`);
    const close=()=>document.getElementById("camera-scan-modal")?.remove();

    document.getElementById("close-camera-scan").onclick=close;
    const info=document.getElementById("camera-lan-info"),scanInput=document.getElementById("camera-cidr"),scanButton=document.getElementById("camera-scan");
    cameraNetworkInfo().then(j=>{scanInput.value=j.lan_cidr||"10.1.1.1/24";info.textContent=(j.lan_cidr?"Mạng LAN: "+j.lan_cidr:"Không lấy được dải LAN")+" • NetBird: "+(j.netbird||"n/a");}).catch(e=>{info.textContent="Không lấy được mạng LAN tự động: "+e.message;});
    scanButton.onclick=async()=>{
      const btn=scanButton,out=document.getElementById("camera-scan-result"),cidr=scanInput.value.trim()||"auto";
      btn.disabled=true;btn.textContent="Đang quét...";out.innerHTML=`<div class="scan-loading">Đang quét ${esc(cidr)}...</div>`;
      try{
        const j=await cameraAction({action:"scan",cidr});
        const items=Array.isArray(j.devices)?j.devices:[];
        if(!items.length)out.innerHTML=`<div class="muted">Không phát hiện thiết bị hoạt động trong dải này.</div>`;
        else{
          out.innerHTML=`<div class="scan-summary">Tìm thấy ${items.length} thiết bị</div>`+items.map(x=>{const proto=String(x.protocol||"HTTP").toUpperCase(),port=x.port||"",vendor=x.vendor||"Unknown",path=x.rtsp_path||"",label=x.name||vendor||x.mac||"Thiết bị";return `<button class="scan-item" data-ip="${esc(x.ip)}" data-protocol="${esc(proto)}" data-port="${esc(port)}" data-vendor="${esc(vendor)}" data-path="${esc(path)}"><span><strong>${esc(label)}</strong><br><span class="small">${esc(x.ip)}${x.mac?" • "+esc(x.mac):""}${proto==="RTSP"&&vendor!=="Unknown"?" • "+esc(vendor):""}</span></span><span class="scan-proto ${proto==="RTSP"?"rtsp":"http"}">${esc(proto)}${port?" :"+esc(port):""} ›</span></button>`}).join("");
          out.querySelectorAll(".scan-item").forEach(item=>item.onclick=()=>{const proto=item.dataset.protocol,ip=item.dataset.ip,port=item.dataset.port,vendor=item.dataset.vendor,path=item.dataset.path; if(proto==="RTSP"){const pre={name:vendor&&vendor!=="Unknown"?vendor+" Camera":"",ip,port:port||"554",path:path||"",username:"",_prefill:true};close();openCameraModal(pre);} else {const u=port?("http://"+ip+":"+port):("http://"+ip);window.open(u,"_blank");}});
        }
      }catch(e){out.innerHTML=`<div class="scan-error">✕ ${esc(e.message)}</div>`;}
      btn.disabled=false;btn.textContent="Quét";
    };
  }

  function openCameraModal(camera=null){
    const editing=!!(camera&&camera.id);
    const c=camera||{name:"",ip:"",port:"554",path:"",username:""};
    document.body.insertAdjacentHTML("beforeend",`<div id="camera-modal" class="modal-overlay"><div class="modal glass"><div class="section-head"><h2>${editing?"Sửa Camera":"Thiết lập Camera"}</h2><span id="close-camera" class="link">✕</span></div><input id="cam-name" class="field" placeholder="Tên camera" value="${esc(c.name||"")}"><input id="cam-ip" class="field" placeholder="Địa chỉ IP" value="${esc(c.ip||"")}"><input id="cam-port" class="field" placeholder="Port RTSP" value="${esc(c.port||"554")}"><input id="cam-path" class="field" placeholder="Đường dẫn RTSP, ví dụ /Streaming/Channels/101" value="${esc(c.path||"")}"><input id="cam-user" class="field" placeholder="Tên đăng nhập" value="${esc(c.username||"")}"><input id="cam-pass" class="field" type="password" placeholder="${editing?"Mật khẩu (để trống = giữ cũ)":"Mật khẩu"}"><div id="cam-result" class="status"></div><div class="modal-actions"><button id="cam-test" class="camera-btn test">Kiểm tra kết nối</button><button id="cam-save" class="primary" style="margin:0">Lưu Camera</button></div></div></div>`);
    document.getElementById("close-camera").onclick=()=>document.getElementById("camera-modal")?.remove();
    document.getElementById("cam-test").onclick=async()=>{const out=document.getElementById("cam-result");out.textContent="Đang kiểm tra...";try{const j=await cameraAction({action:"test_form",name:document.getElementById("cam-name").value.trim(),ip:document.getElementById("cam-ip").value.trim(),port:document.getElementById("cam-port").value.trim()||"554",rtsp_path:document.getElementById("cam-path").value.trim(),username:document.getElementById("cam-user").value.trim(),password:document.getElementById("cam-pass").value});out.textContent=j.ok?"✓ "+j.message+(j.streams?" • "+j.streams:""):"✕ "+(j.error||"Không kết nối");}catch(e){out.textContent="✕ "+e.message;}};
    document.getElementById("cam-save").onclick=async()=>{const out=document.getElementById("cam-result");out.textContent="Đang lưu...";try{const id=editing?camera.id:"";await cameraAction({action:"save",id,name:document.getElementById("cam-name").value.trim(),ip:document.getElementById("cam-ip").value.trim(),port:document.getElementById("cam-port").value.trim()||"554",rtsp_path:document.getElementById("cam-path").value.trim(),username:document.getElementById("cam-user").value.trim(),password:document.getElementById("cam-pass").value});await loadCameras();document.getElementById("camera-modal")?.remove();render();}catch(e){out.textContent="✕ "+e.message;}};
  }

  function bindCameraButtons(){
    document.querySelectorAll(".camera-btn.play").forEach(b=>b.onclick=e=>{e.stopPropagation();startCamera(b.dataset.camera,b);});
    document.querySelectorAll(".camera-btn.test").forEach(b=>b.onclick=async e=>{e.stopPropagation();b.disabled=true;b.textContent="Đang kiểm tra...";try{const j=await cameraAction({action:"test",id:b.dataset.camera});b.textContent=j.ok?"✓ Kết nối OK":"✕ Không kết nối";}catch(err){b.textContent="✕ Lỗi";}setTimeout(()=>{b.disabled=false;b.textContent="Kiểm tra";},1800);});
    document.querySelectorAll(".camera-btn.danger").forEach(b=>b.onclick=async e=>{e.stopPropagation();if(!confirm("Xóa camera này?"))return;try{await stopCamera(b.dataset.camera);await cameraAction({action:"delete",id:b.dataset.camera});await loadCameras();render();}catch(err){alert(err.message);}});
  }

  async function startCamera(id,button){
    const video=document.getElementById("cam-video-"+id),placeholder=document.getElementById("cam-placeholder-"+id);if(!video)return;button.disabled=true;button.textContent="Đang mở...";
    try{const j=await cameraAction({action:"stream",id});if(!j.url)throw new Error("Không nhận được luồng HLS");const src=j.url+"?t="+Date.now();placeholder.style.display="none";video.style.display="block";
      if(window.Hls&&Hls.isSupported()){if(hlsPlayers[id])hlsPlayers[id].destroy();const h=new Hls({lowLatencyMode:true,maxLiveSyncPlaybackRate:1.5});h.loadSource(src);h.attachMedia(video);hlsPlayers[id]=h;h.on(Hls.Events.MANIFEST_PARSED,()=>video.play().catch(()=>{}));}
      else if(video.canPlayType("application/vnd.apple.mpegurl")){video.src=src;video.play().catch(()=>{});} else throw new Error("Trình duyệt không hỗ trợ HLS");
      button.textContent="■ Đang xem";
    }catch(e){button.disabled=false;button.textContent="▶ Xem trực tiếp";alert(e.message);}
  }

  async function stopCamera(id){if(hlsPlayers[id]){hlsPlayers[id].destroy();delete hlsPlayers[id];}try{await cameraAction({action:"stop",id});}catch(_e){}}

  function updateOverview(){
    const t=[...data.traffic].sort((a,b)=>(Number(b.rx_bytes)+Number(b.tx_bytes))-(Number(a.rx_bytes)+Number(a.tx_bytes)));
    const rx=t.reduce((s,x)=>s+Number(x.rx_bytes||0),0),tx=t.reduce((s,x)=>s+Number(x.tx_bytes||0),0);
    const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};set("total-rx",bytes(rx));set("total-tx",bytes(tx));set("total-devices",String(t.length));set("status","● Đang kết nối • "+lastUpdated);
  }
  function updateDevice(){
    const d=data.traffic.find(t=>String(t.mac||"").toLowerCase()===String(selectedMac||"").toLowerCase());if(!d)return;
    const sp=speedByMac.get(String(d.mac).toLowerCase())||{rxBps:0,txBps:0};const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
    set("device-rx-total",bytes(d.rx_bytes));set("device-tx-total",bytes(d.tx_bytes));set("device-conns",String(Number(d.conns||0)));set("device-rx-speed",speed(sp.rxBps));set("device-tx-speed",speed(sp.txBps));
  }

  async function tick(){if(!key)return;try{await load();await loadCameras();if(userInteracting)return;if(page==="overview")updateOverview();else if(page==="device")updateDevice();const s=document.getElementById("status");if(s)s.textContent="● Đang kết nối • "+lastUpdated;}catch(e){const s=document.getElementById("status");if(s)s.textContent="● API lỗi — đang thử lại";}}
  function render(){if(!key)return renderLogin();if(page==="overview")renderOverview();else if(page==="camera")renderCamera();else if(page==="device")renderDevice();else if(page==="web")renderWeb();else if(page==="stats")renderStats();else renderSettings();}
  window.addEventListener("touchstart",()=>{userInteracting=true;},{passive:true});window.addEventListener("touchend",()=>setTimeout(()=>{userInteracting=false;saveUiState();},350),{passive:true});
  async function boot(){renderLogin();if(key){try{await load();await loadCameras();render();}catch(e){renderLogin("Phiên cũ không kết nối được: "+e.message);}}if(timer)clearInterval(timer);timer=setInterval(()=>{tick().catch(()=>{});},3000);}
  boot();
})();