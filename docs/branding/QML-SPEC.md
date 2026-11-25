# Kosmos Overlay — especificação técnica de portabilidade

Documento normativo para reproduzir o motor aprovado, não uma implementação QML. Fontes executáveis canônicas: `tools/motion-lab/source/{geometry,motion,events}.js`; orquestração de referência em `lab-phase-c.js`. Dados: `assets/branding/core/motion-spec.json` (coordenadas normalizadas, cores, tempos, eixos e pesos) e `reference-samples.json` (113 poses e caminhos de referência). Os números do JSON foram extraídos dos caminhos de origem arredondados em 4 casas; a fonte JS mantém os cálculos originais. Use tempo monotônico em ms, floats double, ângulos em radianos.

## 1. Geometria e morph

ViewBox [0,0,320,320]. Órbita: M(x,y), oito segmentos C(x1,y1,x2,y2,x,y), Z, pontos homólogos. `motion-spec.json` contém as duas listas completas e centros/raios. Eixos de deformação fixos: U=(0.78,-sqrt(1-0.78²)), V=(-Uy,Ux), centro C=(160,160). Não há rotação de orientação. O círculo possui centro óptico A=(153.1,174.72), B=(155.4,164.14), raio exterior A=68.08, B=26.22; raio interior A=45.54, B=0. O pequeno deslocamento interno do branco é herdado da aprovação, não translação do conjunto.

Pose = {m∈[0,1], breath∈[0,1], d=[n,ax,tr,alt,th,tip]}. `m=0` institucional; `m=1,d=0` Core. Cada coordenada, raio, centro e canal RGB é interpolado `lerp(a,b,m)=a+(b-a)m`. Clearance de recorte `5.5(1-m)`. Gradiente em coordenadas locais (50,250)→(270,75), stops 0/1, cores do JSON. Núcleo Starlight. A respiração multiplica ambos os raios por `1+0.008*clamp(breath)*(1-m)`.

Easing `S(q)=q³(10−15q+6q²)`, q clampado. Awakening: m=S(t/1200), Sleeping: m=1−S(t/1200); breath=0,d=0. Standby: m=0, breath=(1−cos(2πt/3200))/2. O caminho branco é formado por círculos concêntricos even-odd (raio interior omitido quando ≤0.001). A órbita cobre parte do anel; máscara de luminância remove interior da órbita mais metade da espessura de clearance (stroke com join round). A folga é alfa real, não preenchimento Void.

## 2. Deformação dos caminhos

Partindo do caminho de fase A (4 casas), multiplique cada componente d por m; para cada par de coordenadas P, compute x,y=P−C; u=x*Ux+y*Uy, v=x*Vx+y*Vy; side=tanh(u/80), end=min(1,abs(u)/125); rad=1+th*weight[i]*0.22. Os 25 pesos de vértices/controles estão no JSON (índice zero inclui M). Então:

```
U = u * (1 + ax + alt*side*0.50) * rad
V = v * (1 + tr - alt*side*0.65) * rad + tip*end*end*12
P' = C + U*axisU + V*axisV
```

Arredondar coordenadas finais a 4 casas para paridade de referência; raio do núcleo multiplicado por (1+n), centro inalterado. Não deformar quando m=0 ou d todo zero. Atenção: o JS atual reconstrói o raio interno de poses intermediárias por parsing do path; use amostras/JS como oráculo em caso de divergência. O modelo numérico recomendado elimina parsing, mas sua equivalência precisa ser testada. Mantenha os pontos iniciais/finais coincidentes.

## 3. Perfis principais (ordem de d fixa)

Defina p=t/período, w(p,k=1,o=0)=sin(2π(kp+o)), s=w(p), c=w(p,1,.25), a=clamp(amplitude,0,1). Todos os vetores abaixo são exatamente os coeficientes de `motion.js`. Períodos Listening/Speaking 4800, Thinking 3200, Executing 1600 ms.

```
Listening: [.015*(1+c)/2+.18*a, .015+.055*a, .012*s+.10*a,
            .014*s, .025+.10*a, .025*s+.05*a]
Thinking:  [.022*s,.018*c,.045*w(p,2),.15*s,
            .045*w(p,1,.15),.11*w(p,1,.25)]
beat=((1-cos(2πp))/2)^2; echo=((1-cos(2π(p-.19)))/2)^3
Executing: [.045*beat,.12*beat-.025,.14*beat-.025,.045*w(p,2),
            .23*echo-.04,.09*beat]
Speaking:  [.025*s+.37*a,.018*s+.065*a,.025*c+.19*a,
            .055*w(p,3)*a,.16*a,.055*w(p,2)+.10*a]
```

## 4. Perfis complementares

`P(p,l,r)=sin²(π(p−l)/(r−l))` para l<p<r, zero nas demais posições. p=clamp(t/D); para Warning/Error persistentes, módulo positivo de D. Confirmation usa p=2πt/3600, b=(1−cos(p))/2. Todos usam pose m=1, breath=0, cores Core.

```
Confirmation: [.055*b,-.04*b,-.065*b,0,.035*b,.032*sin(p)]
Success D=1500: a=P(p,0,.65); b=P(p,.30,.95)
 [.29*a,.085*a-.025*b,.115*a-.035*b,.025*b,-.09*b,.06*a-.04*b]
Notification D=1400: v=P(p,0,.33)+.78*P(p,.37,.75)
 [.13*v,.045*v,.10*v,0,.08*v,.05*v]
Warning D=2200: a=P(p,0,.30); b=P(p,.30,.69); c=P(p,.09,.42)
 [.14*a+.10*b,-.105*c+.07*b,-.12*c+.085*b,.045*(a-b),.13*(a+b),-.075*c]
Error D=2000: a=P(p,0,.55); b=P(p,.38,.89)
 [-.27*a+.055*b,-.08*a+.028*b,-.13*a+.045*b,.115*a-.035*b,.12*a-.035*b,-.13*a+.04*b]
```

Confirmation persists until an explicit external decision. Success/Notification one-shot. Warning/Error one-shot default or repeating until cancelled; disabling repeat completes current cycle. Events start/end neutral; exported frames add 250 ms neutral hold. No green/amber/red.

## 5. State and transition policy

Keep separate requested stable state, visual mode, current pose, monotonic phase time, pending event (ID, previous stable, policy, repeat, start, done), transition (from, target, start, duration, live) and sequence for demonstrations only. On a new request, capture **currently displayed** pose before canceling queue. Interpolate every pose component using S(q) from the snapshot; active loop destinations are evaluated live as in JS. Never restart from hardcoded frame zero during interruption. C0 continuity, not guaranteed C1 velocity continuity. Full morph is 1200 ms, partial morph `max(250,1200*distance)`. Active switch 450 ms. Events normalize to neutral 450 ms and start timer only after entrance. Before Sleeping normalize any active deformation to Core in 300 ms; explicit Core normalization 350 ms; breath reset 250 ms. On exit of morph, go Core/Standby. Preserve latest stable non-event as return destination, not a stack; replay restarts phase. Allow explicit destination or hold neutral. Cancel timers on replacement; stale event IDs cannot trigger completion. The visual layer never authorizes work.

## 6. Audio

Amplitude ∈[0,1], supplied separately for microphone and TTS; select by Listening/Speaking. Prototype uses a single channel for demonstration only. RMS sqrt(mean(x²)) for 1024 float samples, mic demo `clamp((rms−.006)*5)`. Real upstream can normalize differently with agreement; do not normalize twice. Filter per frame: dt=clamp(now−last,0,100) ms, τ=65 ms when target>filtered else 160 ms, `filtered+=(target-filtered)*(1−exp(−dt/τ))`. Automatic simulator uses 4800-ms circular phase, bursts in JSON (center,width,amplitude), contribution `a*cos²(π*distance/(2*width))` within width, sum clamp. No recording, network or synthesis required by render layer.

## 7. Rendering options in Qt Quick

**Recommended first spike:** Shape + two ShapePaths, explicit PathMove/PathCubic for the eight segments and ring as two arcs/ellipses; bind real properties/point arrays, fillRule OddEvenFill, no outline except mask. ShapePath LinearGradient must use same local 320-unit coordinates and interpolate sRGB stops (verify parity). Compare default GeometryRenderer and CurveRenderer if supported by pinned Qt version; dynamic tessellation/CPU and anti-aliasing may differ. Use a single clock (`FrameAnimation` if available or animation driver), compute pure poses once per tick, batch updates. `NumberAnimation` alone is insufficient for procedural profiles and interruptible live destinations; animate a scalar progress with custom S or compute directly. A plain SVG `Image` is acceptable for static assets but not for dynamic morph; SVG mask support differs by renderer, do not assume parity.

**Clearance alternatives:** 1) Compute actual path difference ring minus stroked orbit using QPainterPath and QPainterPathStroker (round join); expose resulting path to QML or use custom painted item. Ensure odd-even ring and close contours, no black fill substituted for alpha; boolean operations may flatten Béziers and cost CPU. 2) Render ring and clearance mask into offscreen texture, apply inverted alpha mask via MultiEffect (or ShaderEffect) and composite orbit on top. SVG uses luminance mask; in QML construct the equivalent alpha mask explicitly, not opaque black/white with alpha=1. Verify inverse semantics and no extra padding; layers cost texture memory/bandwidth. 3) Canvas/painted item with destination-out or QPainter composition can be a parity baseline, but benchmark CPU/upload. `clip:true` is rectangular and cannot implement the orbital cutout. Do not paint Void over transparency. Test DPR, premultiplied alpha, anti-aliasing, gradient interpolation, Qt version support and GPU/software fallback.

Window transparent where supported; choose compositor/window flags later on Linux (Wayland/X11 differ). Scale uniformly, position anchor independently of shape. No per-frame SVG parsing or raster GIF playback in production. Benchmark at 64–128 logical px, DPR 1/2, 30/60 fps, frame pacing, CPU/GPU/power, hidden overlay pausing; no native performance claims until measured. Reduced-motion accessibility proposal: optional static representative pose with short opacity transition, no changes to default profile; determine behavior/labels with Desktop Experience. Not implemented in this lab to preserve approved motion.

Qt documentation consulted (version-specific APIs must be confirmed against the chosen PySide6 build):
- https://doc.qt.io/qt-6/qtquick-shapes-qmlmodule.html
- https://doc.qt.io/qt-6/qml-qtquick-shapes-shape.html
- https://doc.qt.io/qt-6/qml-qtquick-shapes-shapepath.html
- https://doc.qt.io/qt-6/qml-qtquick-effects-multieffect.html
- https://doc.qt.io/qt-6/qml-qtquick-shadereffectsource.html

## 8. Acceptance of future port

Use `reference-samples.json` for numerical comparison (target tolerance ≤0.01 viewBox units where comparable). Compare all 12 states, masks on black/white/checker, endpoints and mid-morph, active interruption, event replacement, real mic/TTS envelopes, DPRs and pixel screenshots; set perceptual tolerances after measuring AA differences. No QML application, renderer or native benchmark is delivered here.
