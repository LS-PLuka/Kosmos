from pathlib import Path
r=Path(__file__).resolve().parent.parent
h=(r/'history/playground-phase-c.html').read_text()
h=h.replace('<title>Kosmos — Motion Lab / Fases A + B</title>','<title>Kosmos — Motion Lab / Final</title>').replace('DARK NEBULA / 03','DARK NEBULA / FINAL').replace('Fases A + B + C — transformação, estados e eventos','Versão final — transformação, estados e eventos')
extra='<section class="panel" id="final-tools" style="margin-top:18px;padding:20px"><h2>Inspeção final</h2><label class="check"><input type="checkbox" id="desktop-preview"> Posicionar símbolo no canto inferior direito da área de teste</label><details><summary>Parâmetros da pose e do tempo</summary><pre id="pose-inspector" style="white-space:pre-wrap;font:12px/1.5 monospace"></pre></details><small>Modo de inspeção: não altera as animações aprovadas.</small></section>'
css='\n.stage.desktop-preview{place-items:end; padding:16px}.stage.desktop-preview #symbol{max-width:100%;max-height:100%}#final-tools summary{cursor:pointer}</style>'
h=h.replace('</style>',css,1).replace('</main>',extra+'</main>',1).replace('</body>','<script>'+(r/'source/final-tools.js').read_text()+'</script></body>')
(r/'index.html').write_text(h)
