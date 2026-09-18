(() => {
  const API = "../cgi-bin/datbeo-traffic";
  const app = document.getElementById("app");
  let key = localStorage.getItem("datbeo_api_key") || "";
  let routerLabel = location.host;
  let data = {traffic:[],leases:[],websites:[]};
  let lastUpdated = "";
  let page = localStorage.getItem("datbeo_page") || "overview";
  let filterIp = localStorage.getItem("datbeo_filter_ip") || null;
  let selectedMac = localStorage.getItem("datbeo_selected_mac") || null;
  let timer = null;
  let userInteracting = false;
  let previousTraffic = new Map();
  let speedByMac = new Map();
  let previousTrafficTime = 0;

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  function saveUiState(){
    localStorage.setItem("datbeo_page", page);
    if(filterIp) localStorage.setItem("datbeo_filter_ip", filterIp);
    else localStorage.removeItem("datbeo_filter_ip");
    if(selectedMac) localStorage.setItem("datbeo_selected_mac", selectedMac);
    else localStorage.removeItem("datbeo_selected_mac");
    localStorage.setItem("datbeo_scroll_y", String(window.scrollY || 0));
  }

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const bytes = n => {
    n = Number(n)||0;
    const u=["B","KB","MB","GB","TB"]; let i=0;
    while(n>=1024 && i<u.length-1){n/=1024;i++;}
    return i===0 ? Math.round(n)+" B" : n.toFixed(1)+" "+u[i];
  };
  const speed = bps => {
    const n = Math.max(0, Number(bps)||0);
    if(n >= 1000000) return (n/1000000).toFixed(1)+" Mbps";
    if(n >= 1000) return (n/1000).toFixed(0)+" Kbps";
    return Math.round(n)+" bps";
  };
  const deviceName = (mac) => {
    const x = data.leases.find(v => String(v.mac||"").toLowerCase()===String(mac||"").toLowerCase());
    return x ? (x.name || "Thiết bị") : "Thiết bị";
  };
  const deviceIp = (mac) => {
    const x = data.leases.find(v => String(v.mac||"").toLowerCase()===String(mac||"").toLowerCase());
    return x ? (x.ip || "") : "";
  };
  const icon = n => /iphone|android|phone|điện thoại/i.test(n) ? "▣" : /laptop|mac|pc|máy/i.test(n) ? "▱" : "◉";

  function renderLogin(msg="") {
    app.innerHTML = `
      <div class="shell"><div class="container">
        <div class="brand">DatBeo Router Monitor</div>
        <div class="sub">OpenWrt Router • NetBird</div>
        <div class="glass login">
          <input id="key" class="field" type="password" placeholder="API KEY" autocomplete="off" value="${esc(key)}">
          <button id="go" class="primary">Đăng nhập</button>
          <div class="hint">Ứng dụng Android chỉ là vỏ. Giao diện này nằm trên router nên có thể cập nhật mà không cần cài APK mới.</div>
          <div class="status">${esc(msg)}</div>
        </div>
      </div></div>`;
    document.getElementById("go").onclick = async () => {
      key = document.getElementById("key").value.trim();
      if(!key) return renderLogin("Nhập API KEY.");
      try {
        await load();
        localStorage.setItem("datbeo_api_key", key);
        page="overview"; saveUiState(); render();
      } catch(e) { renderLogin("Không kết nối được API: "+e.message); }
    };
  }

  function safeJson(text){
    try { return JSON.parse(text); }
    catch(e){
      const fixed=text.trim().replace(/("traffic"\s*:\s*)\[\s*,\s*/,"$1[");
      return JSON.parse(fixed);
    }
  }

  async function load(){
    const r = await fetch(API+"?key="+encodeURIComponent(key), {cache:"no-store"});
    const text = await r.text();
    if(!r.ok) throw new Error("HTTP "+r.status);
    const j = safeJson(text);
    if(j.error) throw new Error(j.error);

    const nextTraffic = Array.isArray(j.traffic) ? j.traffic : [];
    const now = Date.now();
    const dt = previousTrafficTime > 0 ? Math.max(0.5, (now - previousTrafficTime) / 1000) : 0;
    const nextSpeed = new Map();

    nextTraffic.forEach(t => {
      const mac = String(t.mac||"").toLowerCase();
      const old = previousTraffic.get(mac);
      const rx = Number(t.rx_bytes||0);
      const tx = Number(t.tx_bytes||0);
      if(old && dt > 0){
        nextSpeed.set(mac, {
          rxBps: Math.max(0, rx - old.rx) * 8 / dt,
          txBps: Math.max(0, tx - old.tx) * 8 / dt
        });
      } else {
        nextSpeed.set(mac, {rxBps:0, txBps:0});
      }
    });

    previousTraffic = new Map(nextTraffic.map(t => [
      String(t.mac||"").toLowerCase(),
      {rx:Number(t.rx_bytes||0), tx:Number(t.tx_bytes||0)}
    ]));
    previousTrafficTime = now;
    speedByMac = nextSpeed;

    data = {
      traffic: nextTraffic,
      leases: Array.isArray(j.leases)?j.leases:[],
      websites: Array.isArray(j.websites)?j.websites:[]
    };
    routerLabel = (j.netbird_ip || location.host);
    lastUpdated = new Date().toLocaleTimeString("vi-VN",{hour12:false});
  }

  function bindNav(){
    document.querySelectorAll(".nav button").forEach(b => {
      b.onclick = () => {
        page = b.dataset.p;
        saveUiState();
        render();
        setTimeout(() => window.scrollTo(0, 0), 0);
      };
    });
  }

  function renderOverview(){
    const traffic=[...data.traffic].sort((a,b)=>(Number(b.rx_bytes)+Number(b.tx_bytes))-(Number(a.rx_bytes)+Number(a.tx_bytes)));
    const totalRx=traffic.reduce((s,x)=>s+Number(x.rx_bytes||0),0);
    const totalTx=traffic.reduce((s,x)=>s+Number(x.tx_bytes||0),0);
    app.innerHTML=`
      <div class="shell"><div class="container">
        <div class="brand">DatBeo Traffic</div>
        <div id="status" class="status">● Đang kết nối • ${esc(lastUpdated)}</div>
        <div style="text-align:center"><span class="pill">◎ ${esc(routerLabel)}</span></div>
        <div class="glass grid3">
          <div class="metric"><div class="icon">↓</div><div class="label">Tải xuống</div><div id="total-rx" class="value">${bytes(totalRx)}</div></div>
          <div class="metric"><div class="icon">↑</div><div class="label">Tải lên</div><div id="total-tx" class="value">${bytes(totalTx)}</div></div>
          <div class="metric"><div class="icon">●</div><div class="label">Thiết bị</div><div id="total-devices" class="value">${traffic.length}</div></div>
        </div>
        <div class="section-head"><h2>Thiết bị</h2></div>
        <div id="devices">
        ${traffic.length ? traffic.map(t=>`
          <div class="glass card device" data-mac="${esc(t.mac)}">
            <div class="iconbox">${icon(deviceName(t.mac))}</div>
            <div><div class="name">${esc(deviceName(t.mac))}</div><div class="small">${esc(deviceIp(t.mac)||t.mac)}</div><div class="small online">● Online • ${Number(t.conns||0)} kết nối</div></div>
            <div class="right"><div>↓ ${bytes(t.rx_bytes)}</div><div>↑ ${bytes(t.tx_bytes)}</div></div>
          </div>`).join("") : '<div class="glass card error">Chưa có dữ liệu traffic.</div>'}
        </div>
        <div class="section-head"><h2>Website đã truy cập</h2><span class="link" id="allweb">Xem tất cả ›</span></div>
        <div id="overview-websites" class="glass card">${renderWebsiteRows(data.websites.slice(0,8))}</div>
        ${nav()}
      </div></div>`;
    document.getElementById("allweb").onclick=()=>{page="web";render();};
    document.querySelectorAll(".device").forEach(el=>el.onclick=()=>{const ip=el.dataset.ip;if(ip){filterIp=ip;page="web";saveUiState();render();}});
    bindNav();
  }

  function currentDevice(){
    return data.traffic.find(t => String(t.mac||"").toLowerCase() === String(selectedMac||"").toLowerCase()) || null;
  }

  function currentDevice(){
    return data.traffic.find(t => String(t.mac||"").toLowerCase() === String(selectedMac||"").toLowerCase()) || null;
  }

  function renderDevice(){
    const d=currentDevice();
    if(!d){ page="overview"; selectedMac=null; saveUiState(); return renderOverview(); }
    const name=deviceName(d.mac);
    const ip=deviceIp(d.mac);
    const mac=d.mac;
    const sp=speedByMac.get(String(mac||"").toLowerCase()) || {rxBps:0,txBps:0};
    const sites=data.websites.filter(x=>x.ip===ip);

    app.innerHTML=`
      <div class="shell"><div class="container">
        <div class="section-head">
          <h2>${esc(name)}</h2>
          <span class="link" id="device-back">‹ Thiết bị</span>
        </div>

        <div class="glass card">
          <div class="small muted">Thông tin thiết bị</div>
          <div class="tableline"><span>Tên</span><span class="domain">${esc(name)}</span></div>
          <div class="tableline"><span>MAC</span><span class="domain">${esc(mac)}</span></div>
          <div class="tableline"><span>IP</span><span class="domain">${esc(ip || "Chưa có")}</span></div>
        </div>

        <div class="glass card grid3">
          <div class="metric"><div class="icon">↓</div><div class="label">Download</div><div id="device-rx-total" class="value">${bytes(d.rx_bytes)}</div></div>
          <div class="metric"><div class="icon">↑</div><div class="label">Upload</div><div id="device-tx-total" class="value">${bytes(d.tx_bytes)}</div></div>
          <div class="metric"><div class="icon">●</div><div class="label">Kết nối</div><div id="device-conns" class="value">${Number(d.conns||0)}</div></div>
        </div>

        <div class="glass card grid3">
          <div class="metric"><div class="icon">↓</div><div class="label">Tốc độ tải xuống</div><div id="device-rx-speed" class="value">${speed(sp.rxBps)}</div></div>
          <div class="metric"><div class="icon">↑</div><div class="label">Tốc độ tải lên</div><div id="device-tx-speed" class="value">${speed(sp.txBps)}</div></div>
          <div class="metric"><div class="icon">◉</div><div class="label">Trạng thái</div><div id="device-online" class="value online">Online</div></div>
        </div>

        <div class="section-head"><h2>Website</h2><span class="small">gần đây</span></div>
        <div id="device-sites" class="glass card">${renderWebsiteRows(sites,50)}</div>
        ${nav()}
      </div></div>`;

    document.getElementById("device-back").onclick=()=>{ page="overview"; selectedMac=null; saveUiState(); render(); };
    bindNav();
  }

  function updateDeviceInPlace(){
    const d=currentDevice();
    if(!d){ page="overview"; selectedMac=null; saveUiState(); return renderOverview(); }
    const set=(id,value)=>{ const el=document.getElementById(id); if(el) el.textContent=value; };
    const sp=speedByMac.get(String(d.mac||"").toLowerCase()) || {rxBps:0,txBps:0};
    set("device-rx-total",bytes(d.rx_bytes));
    set("device-tx-total",bytes(d.tx_bytes));
    set("device-conns",String(Number(d.conns||0)));
    set("device-rx-speed",speed(sp.rxBps));
    set("device-tx-speed",speed(sp.txBps));
    const box=document.getElementById("device-sites");
    if(box) box.innerHTML=renderWebsiteRows(data.websites.filter(x=>x.ip===deviceIp(d.mac)),50);
  }
  function renderWeb(){
    const ips=[...new Set(data.websites.map(x=>x.ip).filter(Boolean))];
    const rows=filterIp ? data.websites.filter(x=>x.ip===filterIp) : data.websites;
    app.innerHTML=`
      <div class="shell"><div class="container">
        <div class="section-head"><h2>Website</h2><span class="link" id="back">‹ Tổng quan</span></div>
        <div class="glass card controls"><select id="filter"><option value="">Tất cả thiết bị</option>${ips.map(ip=>`<option value="${esc(ip)}" ${filterIp===ip?"selected":""}>${esc(ip)}</option>`).join("")}</select></div>
        <div id="web-rows" class="glass card">${renderWebsiteRows(rows,200)}</div>
        ${nav()}
      </div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";filterIp=null;saveUiState();render();};
    document.getElementById("filter").onchange=e=>{filterIp=e.target.value||null;saveUiState();render();};
    bindNav();
  }

  function renderWebsiteRows(rows,limit=8){
    const shown=rows.slice(-limit).reverse();
    if(!shown.length) return '<div class="muted">Chưa có dữ liệu DNS. Hãy bật DNS logging trên OpenWrt.</div>';
    return shown.map(x=>`<div class="tableline"><span>◎</span><span class="domain">${esc(x.domain)}</span><span class="small">${esc(x.time)}</span></div>`).join("");
  }

  function nav(){
    return `<div class="glass nav">
      <button data-p="overview">⌂<br><span class="small">Tổng quan</span></button>
      <button data-p="web">◎<br><span class="small">Website</span></button>
      <button data-p="stats">▥<br><span class="small">Thống kê</span></button>
      <button data-p="settings">⚙<br><span class="small">Cài đặt</span></button>
    </div>`;
  }

  function updateOverviewInPlace(){
    const traffic=[...data.traffic].sort((a,b)=>
      (Number(b.rx_bytes)+Number(b.tx_bytes))-(Number(a.rx_bytes)+Number(a.tx_bytes))
    );
    const totalRx=traffic.reduce((s,x)=>s+Number(x.rx_bytes||0),0);
    const totalTx=traffic.reduce((s,x)=>s+Number(x.tx_bytes||0),0);

    const set=(id,value)=>{
      const el=document.getElementById(id);
      if(el) el.textContent=value;
    };
    set("total-rx",bytes(totalRx));
    set("total-tx",bytes(totalTx));
    set("total-devices",String(traffic.length));
    set("status","● Đang kết nối • "+lastUpdated);

    const devices=document.getElementById("devices");
    if(devices){
      devices.innerHTML=traffic.length ? traffic.map(t=>`
        <div class="glass card device" data-mac="${esc(t.mac)}">
          <div class="iconbox">${icon(deviceName(t.mac))}</div>
          <div>
            <div class="name">${esc(deviceName(t.mac))}</div>
            <div class="small">${esc(deviceIp(t.mac)||t.mac)}</div>
            <div class="small online">● Online • ${Number(t.conns||0)} kết nối</div>
          </div>
          <div class="right"><div>↓ ${bytes(t.rx_bytes)}</div><div>↑ ${bytes(t.tx_bytes)}</div></div>
        </div>`).join("") :
        '<div class="glass card error">Chưa có dữ liệu traffic.</div>';
      document.querySelectorAll("#devices .device").forEach(el=>{
        el.onclick=()=>{
          const mac=el.dataset.mac;
          if(mac){selectedMac=mac;page="device";saveUiState();render();}
        };
      });
    }

    const ow=document.getElementById("overview-websites");
    if(ow) ow.innerHTML=renderWebsiteRows(data.websites.slice(0,8));
  }

  function updateWebInPlace(){
    const rows=filterIp ? data.websites.filter(x=>x.ip===filterIp) : data.websites;
    const box=document.getElementById("web-rows");
    if(box) box.innerHTML=renderWebsiteRows(rows,200);
  }

  function updateStatsInPlace(){
    const traffic=data.traffic;
    const top=[...traffic].sort((a,b)=>
      Number(b.rx_bytes)+Number(b.tx_bytes)-Number(a.rx_bytes)-Number(a.tx_bytes)
    );
    const box=document.getElementById("stats-rows");
    if(box){
      box.innerHTML=top.length ? top.map(t=>`
        <div class="tableline">
          <span class="domain">${esc(deviceName(t.mac))}</span>
          <span>↓ ${bytes(t.rx_bytes)} • ↑ ${bytes(t.tx_bytes)}</span>
        </div>`).join("") : 'Chưa có dữ liệu.';
    }
  }

  function renderStats(){
    const traffic=data.traffic;
    const top=[...traffic].sort((a,b)=>Number(b.rx_bytes)+Number(b.tx_bytes)-Number(a.rx_bytes)-Number(a.tx_bytes));
    app.innerHTML=`<div class="shell"><div class="container">
      <div class="section-head"><h2>Thống kê</h2><span class="link" id="back">‹ Tổng quan</span></div>
      <div id="stats-rows" class="glass card">${top.length?top.map(t=>`<div class="tableline"><span class="domain">${esc(deviceName(t.mac))}</span><span>↓ ${bytes(t.rx_bytes)} • ↑ ${bytes(t.tx_bytes)}</span></div>`).join(""):'Chưa có dữ liệu.'}</div>
      ${nav()}
    </div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";saveUiState();render();};
    bindNav();
  }

  function renderSettings(){
    app.innerHTML=`<div class="shell"><div class="container">
      <div class="section-head"><h2>Cài đặt</h2><span class="link" id="back">‹ Tổng quan</span></div>
      <div class="glass card">
        <div class="small">Router</div><div class="name">${esc(location.host)}</div>
        <button id="logout" class="primary" style="margin-top:16px">Xóa KEY và đăng xuất</button>
      </div>
      ${nav()}
    </div></div>`;
    document.getElementById("back").onclick=()=>{page="overview";render();};
    document.getElementById("logout").onclick=()=>{localStorage.removeItem("datbeo_api_key");localStorage.removeItem("datbeo_page");localStorage.removeItem("datbeo_filter_ip");key="";page="overview";filterIp=null;renderLogin();};
    bindNav();
  }

  function render(){
    if(!key) return renderLogin();
    if(page==="overview") renderOverview();
    else if(page==="device") renderDevice();
    else if(page==="web") renderWeb();
    else if(page==="stats") renderStats();
    else renderSettings();
  }

  async function tick(){
    if(!key) return;
    try {
      await load();
      if(userInteracting) return;
      if(page==="overview") updateOverviewInPlace();
      else if(page==="device") updateDeviceInPlace();
      else if(page==="web") updateWebInPlace();
      else if(page==="stats") updateStatsInPlace();

      const s=document.getElementById("status");
      if(s) s.textContent="● Đang kết nối • "+lastUpdated;
    } catch(e){
      const s=document.getElementById("status");
      if(s) s.textContent="● API lỗi — đang thử lại";
    }
  }

  window.addEventListener("touchstart", () => { userInteracting = true; }, {passive:true});
  window.addEventListener("touchend", () => {
    setTimeout(() => { userInteracting = false; saveUiState(); }, 350);
  }, {passive:true});

  render();
  const savedScroll = Number(localStorage.getItem("datbeo_scroll_y") || 0);
  if(savedScroll > 0) setTimeout(() => window.scrollTo(0, savedScroll), 60);

  if(key) tick().catch(()=>{});
  if(timer) clearInterval(timer);
  timer=setInterval(tick,3000);
})();