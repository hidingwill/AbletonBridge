"""Dashboard HTML template for AbletonBridge.

Contains the single-page HTML/CSS/JS dashboard served by the status server.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AbletonBridge — Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: #0d1117; color: #c9d1d9; line-height: 1.5;
  }
  .container { max-width: 960px; margin: 0 auto; padding: 24px; }
  h1 { color: #58a6ff; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #8b949e; font-size: 0.85rem; margin-bottom: 24px; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px; margin-bottom: 24px;
  }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;
  }
  .card-label {
    font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em;
  }
  .card-value { font-size: 1.5rem; font-weight: 600; margin-top: 4px; }
  .status-ok  { color: #3fb950; }
  .status-err { color: #f85149; }
  .status-warn { color: #d29922; }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; color: #8b949e; font-size: 0.75rem; text-transform: uppercase;
    padding: 8px 12px; border-bottom: 1px solid #30363d;
  }
  td { padding: 6px 12px; border-bottom: 1px solid #21262d; font-size: 0.85rem; }
  tr:hover { background: #161b22; }
  .error-cell { color: #f85149; }
  .section {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 16px; margin-bottom: 24px;
  }
  .section h2 { font-size: 1rem; color: #58a6ff; margin-bottom: 12px; }
  .refresh-bar {
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;
  }
  .refresh-bar span { font-size: 0.75rem; color: #8b949e; }
  #countdown { color: #58a6ff; }
  .bar-row {
    display: flex; align-items: center; margin-bottom: 6px; font-size: 0.8rem;
  }
  .bar-name { width: 240px; color: #8b949e; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar-track { flex: 1; background: #21262d; border-radius: 4px; height: 20px; position: relative; }
  .bar-fill { background: #1f6feb; border-radius: 4px; height: 100%; min-width: 2px; }
  .bar-count { position: absolute; top: 0; left: 8px; line-height: 20px; font-size: 0.7rem; color: #c9d1d9; }
  .empty-msg { color: #484f58; font-style: italic; font-size: 0.85rem; }
  .status-banner {
    padding: 10px 16px; border-radius: 8px; margin-bottom: 16px;
    font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 8px;
  }
  .status-banner .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .banner-ok { background: #0d2818; border: 1px solid #238636; color: #3fb950; }
  .banner-ok .dot { background: #3fb950; }
  .banner-warn { background: #2a1f00; border: 1px solid #9e6a03; color: #d29922; }
  .banner-warn .dot { background: #d29922; }
  .banner-err { background: #2d0a0a; border: 1px solid #da3633; color: #f85149; }
  .banner-err .dot { background: #f85149; }
</style>
</head>
<body>
<div class="container">
  <div class="refresh-bar">
    <div><h1>AbletonBridge</h1><div class="subtitle">Status Dashboard</div></div>
    <span>Refresh in <span id="countdown">3</span>s</span>
  </div>
  <div id="status-banner"></div>
  <div class="grid" id="cards"></div>
  <div class="section" id="top-tools-section"></div>
  <div class="section">
    <h2>Recent Tool Calls</h2>
    <div id="log-area"></div>
  </div>
  <div class="section">
    <h2>Server Log</h2>
    <div id="server-log" style="
      background:#0d1117; border:1px solid #30363d; border-radius:6px;
      padding:12px; max-height:400px; overflow-y:auto; font-family:'Cascadia Code','Fira Code','Consolas',monospace;
      font-size:0.78rem; line-height:1.6;
    "></div>
  </div>
</div>
<script>
const REFRESH_MS = 3000;
let countdown = 3;
function fmtUp(s) {
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = Math.floor(s%60);
  return (h>0?h+'h ':'')+(m>0?m+'m ':'')+sec+'s';
}
async function refresh() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    // Status banner
    const sb = document.getElementById('status-banner');
    if (d.ableton_connected && d.m4l_connected) {
      sb.innerHTML = '<div class="status-banner banner-ok"><span class="dot"></span>All systems operational — Ableton + M4L Bridge connected and ready</div>';
    } else if (d.ableton_connected && !d.m4l_connected) {
      sb.innerHTML = '<div class="status-banner banner-warn"><span class="dot"></span>Ableton connected — M4L Bridge '+(d.m4l_sockets_ready?'waiting for device response':'not connected')+'</div>';
    } else {
      sb.innerHTML = '<div class="status-banner banner-err"><span class="dot"></span>Ableton not connected — make sure the Remote Script is loaded</div>';
    }
    document.getElementById('cards').innerHTML = [
      card('Server Version', d.version, ''),
      card('Uptime', fmtUp(d.uptime_seconds), ''),
      card('Ableton', d.ableton_connected?'Connected':'Disconnected',
           d.ableton_connected?'status-ok':'status-err'),
      card('M4L Bridge',
           d.m4l_connected?'Connected':d.m4l_sockets_ready?'Sockets Ready':'Disconnected',
           d.m4l_connected?'status-ok':d.m4l_sockets_ready?'status-warn':'status-err'),
      card('Snapshots', d.store_counts.snapshots, ''),
      card('Macros', d.store_counts.macros, ''),
      card('Param Maps', d.store_counts.param_maps, ''),
      card('Total Tool Calls', d.total_tool_calls, ''),
    ].join('');
    // Top tools
    const tt = document.getElementById('top-tools-section');
    if (d.top_tools.length) {
      const max = d.top_tools[0][1];
      tt.innerHTML = '<h2>Most Used Tools</h2>' + d.top_tools.map(([n,c])=>
        '<div class="bar-row"><span class="bar-name">'+n+'</span>'+
        '<div class="bar-track"><div class="bar-fill" style="width:'+(c/max*100).toFixed(1)+'%"></div>'+
        '<span class="bar-count">'+c+'</span></div></div>'
      ).join('');
    } else { tt.innerHTML = '<h2>Most Used Tools</h2><p class="empty-msg">No tool calls yet</p>'; }
    // Log
    const la = document.getElementById('log-area');
    if (d.recent_calls.length) {
      la.innerHTML = '<table><thead><tr><th>Time</th><th>Tool</th><th>Duration</th><th>Args</th><th>Status</th></tr></thead><tbody>'+
        d.recent_calls.slice().reverse().map(e=>
          '<tr><td>'+(e.timestamp.split('T')[1]||'').slice(0,8)+'</td>'+
          '<td>'+e.tool+'</td><td>'+e.duration_ms+'ms</td>'+
          '<td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+(e.args_summary||'')+'</td>'+
          '<td class="'+(e.error?'error-cell':'')+'">'+(e.error||'OK')+'</td></tr>'
        ).join('')+'</tbody></table>';
    } else { la.innerHTML = '<p class="empty-msg">No tool calls yet</p>'; }
    // Server log
    const sl = document.getElementById('server-log');
    if (d.server_logs && d.server_logs.length) {
      const colors = {INFO:'#8b949e',WARNING:'#d29922',ERROR:'#f85149',DEBUG:'#484f58',CRITICAL:'#f85149'};
      sl.innerHTML = d.server_logs.map(e=>{
        const c = colors[e.level]||'#8b949e';
        const lvl = e.level.padEnd(7);
        return '<div><span style="color:#484f58">'+e.ts+'</span> <span style="color:'+c+'">'+
               lvl+'</span> '+escHtml(e.msg)+'</div>';
      }).join('');
      sl.scrollTop = sl.scrollHeight;
    } else { sl.innerHTML = '<div style="color:#484f58;font-style:italic">No log entries yet</div>'; }
  } catch(err) { console.error('Dashboard refresh failed:', err); }
  countdown = REFRESH_MS/1000;
}
function card(label, value, cls) {
  return '<div class="card"><div class="card-label">'+label+'</div>'+
         '<div class="card-value '+(cls||'')+'">'+value+'</div></div>';
}
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
refresh();
setInterval(refresh, REFRESH_MS);
setInterval(()=>{countdown=Math.max(0,countdown-1);
  document.getElementById('countdown').textContent=countdown;},1000);
</script>
</body>
</html>"""
