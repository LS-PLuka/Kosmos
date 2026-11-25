# Kosmos Motion Lab — Phase B

## Uso

Abra `previews/playground-phase-b.html` em um navegador moderno. É um HTML autônomo, sem dependências externas. O playground anterior (`previews/playground.html`) e todos os recursos da Fase A foram preservados sem alteração de conteúdo. A Fase C não está implementada.

- Ativar/Desativar: transformação original; a ativação termina na pose Core aprovada.
- Estados ativos: escolha Listening, Thinking, Executing ou Speaking, inclusive durante uma transição.
- Ciclo de transformação: reproduz o fluxo A isolado. Fluxo completo: percorre os estados A+B e retorna a Standby.
- A simulação automática inicia selecionada. O slider (0–100%) troca para manual. Thinking e Executing não dependem do áudio. O microfone, quando selecionado, requer autorização; serve para experimentar ambas as reações de voz, não é um sintetizador.
- O tamanho (16–400 px), fundo e inspeção manual do morphing continuam disponíveis. O slider de morphing é uma inspeção direta, não uma transição animada.
- No fundo claro Starlight o núcleo tem pouco contraste, como já registrado na Fase A; não houve alteração de cores.

### Microfone

A página não pede permissão automaticamente. Se o navegador bloquear `file://`, extraia o ZIP, abra um terminal na pasta `kosmos-motion-ab` e execute `python3 -m http.server 8765 --bind 127.0.0.1`. Abra `http://localhost:8765/previews/playground-phase-b.html`. A captura utiliza `getUserMedia` e Web Audio, apenas localmente, sem gravação, reprodução ou envio. O botão de desligar, mudança de fonte ou saída da página encerra os tracks; uma autorização tardia após cancelamento também encerra os tracks. A fonte manual permanece disponível caso a permissão seja negada. A entrada é RMS normalizada, com piso de ruído e ganho fixos, sem calibração automática. Para Speaking, a futura entrada deve ser amplitude do áudio TTS, não do microfone.

## Comportamento e tempos

| Estado | Loop | Movimento |
|---|---:|---|
| Listening | 4800 ms | Pulsos receptivos espaçados, expansão transversal e núcleo proporcional à amplitude (até +18% em relação ao raio-base, além da respiração de até 1,5%). |
| Thinking | 3200 ms | Deformação alternada das extremidades e ondulação lenta. Núcleo ±2,2%. |
| Executing | 1600 ms | Impulso determinado de expansão e espessamento com defasagem, núcleo até +4,5%. |
| Speaking | 4800 ms | Pulsos irregulares simulados, raio até +37% pela amplitude, além da oscilação de ±2,5%; órbita acompanha a expressão. |

Os loops são periódicos, sem frame duplicado no fechamento. Os GIFs têm fundo Void, os WebPs têm alfa e compressão lossless; 320×320, ~30 FPS. As amostras de áudio dos arquivos são sintéticas (não reativas), com envelopes de cosseno de larguras e amplitudes diferentes. O HTML calcula o estado continuamente e filtra amplitude com ataque de 65 ms e relaxamento de 160 ms. As variações são dimensionais, sem rotação, partículas ou novas cores.

## Geometria e continuidade

`source/geometry.js` é idêntico ao da Fase A. A extensão `source/motion.js` recebe `m`, `breath` e seis parâmetros adimensionais: raio do núcleo, expansão longitudinal, expansão transversal, alternância das extremidades, espessura e flexão das pontas. Atua sobre os pontos de controle da órbita original em eixos diagonais fixos. A posição do núcleo segue a geometria A, sem deslocamento adicional. Quando todos os parâmetros são zero, a forma resultante é exatamente a forma A. A deformação é multiplicada por `m`; a máscara e a órbita recebem a mesma curva. O gradiente é o original.

Trocas de estado capturam a pose corrente e interpolam os parâmetros com `ease` quintic smoothstep. Entrada a partir de repouso passa por Awakening original (1200 ms em curso completo), depois aplica a deformação de destino em 450 ms. Ao desativar um estado ativo, o Core retorna à pose neutra em 300 ms antes de Sleeping original (1200 ms em curso completo). Interrupções partem da pose exibida, não do primeiro frame. A continuidade garantida é de posição/forma (C0), não conservação exata da velocidade durante interrupções. A escala varia intencionalmente, não há translação global nem transformação angular.

## Fontes e reprodução

- `source/motion.js`: extensão de geometria e perfis de movimento; módulo Node/browser.
- `source/lab-phase-b.js`: máquina de estados, transições, entradas de áudio e renderização SVG.
- `source/build-phase-b.py`: gera o HTML autônomo a partir da base original e dos módulos.
- `source/render-phase-b.js`: sequências SVG para os quatro loops.
- `source/export-phase-b.py`: rasterização Chromium e exportação Pillow; não reexporta arquivos A.
- `source/test-phase-b.js` e `source/test-lab.py`: validações automatizadas.

Com Node.js, Python 3, Pillow, Playwright e Chromium:

```sh
pip install pillow playwright
python source/build-phase-b.py
python source/export-phase-b.py
node source/test-phase-b.js
python source/test-lab.py
```

## Portabilidade QML

Portar `shape` da Fase A e os seis parâmetros de deformação da Fase B para um componente Qt Quick. A órbita pode ser um ShapePath com PathCubic; aplicar os pontos interpolados tanto à curva visível quanto ao recorte. Manter o gradiente e o sistema de coordenadas 320×320. Usar propriedades reais para `m`, `breath`, amplitude suavizada e vetor de deformação. Capturar a pose ao trocar estados; calcular a interpolação e os envelopes usando o relógio de animação. Não usar GIF como motor reativo. O teste automatizado em Chromium injeta um stream Web Audio local de teste, pois o ambiente de execução bloqueia navegação direta para file:// e localhost. Isso verifica o pipeline do analisador, desligamento e tratamento de negação simulada, mas não valida um microfone físico nem a janela de autorização real. O teste de QML nativo e desempenho no desktop Linux ficam pendentes; nenhuma integração com assistente/TTS foi feita.
