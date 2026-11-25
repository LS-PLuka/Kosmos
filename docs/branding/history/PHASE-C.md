# Kosmos Motion Lab — Phase C

A extensão preserva os arquivos de A+B byte a byte. `previews/playground-phase-c.html` é uma nova versão autônoma; as duas anteriores permanecem disponíveis. Abra o HTML em um navegador moderno, sem dependências de rede. Não há integração QML nesta fase.

## Perfis e tempos

| Estado | Modelo | Duração | Movimento |
|---|---|---:|---|
| Confirmation | Persistente | 3600 ms/ciclo | Núcleo até +5,5% de raio; aproximação transversal/longitudinal e flexão discreta das pontas. |
| Success | Evento | 1500 ms | Expansão até +29% do raio, seguida de relaxamento da órbita, sem ícone ou nova cor. |
| Notification | Evento | 1400 ms | Dois pulsos de amplitudes diferentes, separados por pausa curta. |
| Warning | Evento ou persistente | 2200 ms | Duas pulsações com estreitamento orbital no primeiro impulso e expansão no segundo. |
| Error | Evento ou persistente | 2000 ms | Contração de até 27% do raio, deformação controlada e recuperação com pequena expansão. |

Os valores são relativos à pose Core. Todos usam as mesmas cores e eixos fixos da Fase B. Os pulsos são envelopes de cosseno elevado, com valor e velocidade zero nas bordas; os perfis começam e terminam na pose neutra. Confirmation é periódico. Warning e Error podem repetir o perfil com pausa interna. A ausência de movimento angular global é intencional. Nenhum novo elemento é desenhado.

## Controles e política de eventos

- Escolha um dos nove estados ativos. O botão Ativar mantém a transformação aprovada; os botões Desativar/Repouso passam pelo Sleeping.
- Confirmation permanece ativo indefinidamente; Autorizar leva a Executing, Recusar a Sleeping → Standby. Os fluxos de demonstração de confirmação aguardam decisão explícita.
- Success e Notification executam uma única vez. Warning e Error são pontuais por padrão; marque Repetir para persistência. A opção pode ser alterada durante o evento. A desativação da repetição termina o ciclo atual.
- Após evento, selecione retorno ao estado não-evento solicitado anteriormente, Core, Speaking, Listening, Thinking, Executing, Confirmation, Standby, ou permanência na pose neutra do evento. Eventos sucessivos preservam o último destino não-evento (não existe pilha de eventos). Retorno ao estado anterior reinicia seu perfil temporal, não restaura a fase exata do loop anterior. Se o evento começa em repouso, Awakening precede o evento e a opção anterior retorna a Standby via Sleeping.
- Os fluxos de demonstração têm destino próprio e não dependem da política global nem da repetição configurada. Escolha um dos sete fluxos C; o fluxo A+B e o ciclo A continuam disponíveis.
- A entrada de eventos normaliza a pose ao Core em 450 ms antes de executar o perfil. Isso mantém o primeiro frame do evento neutro, mesmo quando interrompe outro estado. A saída utiliza as transições A+B existentes. Durante interrupções captura-se a pose exibida e interpola-se via quintic smoothstep. Continuidade de posição/forma (C0), não necessariamente de velocidade (C1). O controle manual do morphing é inspeção direta, não uma transição animada.
- Áudio, simulador, microfone opcional, dimensão 16–400 px e fundos são mantidos. A implementação não grava ou transmite áudio. Para microfone, consulte PHASE-B.md; use localhost quando necessário: `python3 -m http.server 8765 --bind 127.0.0.1`, depois `http://localhost:8765/previews/playground-phase-c.html`.
- Em fundo Starlight o núcleo tem contraste reduzido, limitação herdada; não alteramos a identidade para corrigi-la.

## Arquitetura e fontes

- `geometry.js` — geometria A, paleta, morphing e easing (inalterado).
- `motion.js` — deformação Bézier, interpolação de poses, perfis e amplitude B (inalterado).
- `events.js` — perfis C, duração, classificação, repetição e resolução de destino. Módulo Node/browser, independente do DOM.
- `lab-phase-c.js` — orquestração de estados/transições/eventos, relógio, áudio filtrado e renderização SVG. Derivado do runtime B sem modificar o original.
- `build-phase-c.py` — produz HTML autônomo a partir do layout B e módulos compartilhados.
- `render-phase-c.js` / `export-phase-c.py` — amostragem e renderização das referências de motion; não reexportam A+B.
- `test-phase-c.js` — perfis, limites, endpoints, 81 pares de interpolação.
- `test-lab-c.py` — fluxos e controles C em Chromium com relógio virtual.
- `test-lab-c-regression.py` — regressão de controles A+B no novo HTML, com stream virtual local; não testa hardware físico.
- `test-exports-c.py` — validação de formatos, alfa, duração, repetição e neutralidade dos endpoints.

GIF: fundo Void, 320×320, aproximadamente 30 FPS. WebP: RGBA lossless, 320×320, aproximadamente 30 FPS. Confirmation repete continuamente; os quatro eventos são exportados como one-shot, com pose final neutra mantida por 250 ms para visualização. Para repetir alertas, use o Motion Lab. Os tempos de entrada/saída do playground não integram os arquivos de evento isolado.

## Reprodução local

Com Node.js, Python 3, Pillow, Playwright e Chromium disponíveis:

```sh
pip install pillow playwright
python source/build-phase-c.py
python source/export-phase-c.py
node source/test-phase-b.js
node source/test-phase-c.js
python source/test-exports-c.py
python source/test-lab-c.py
python source/test-lab-c-regression.py
```

## QML — próxima fase

Portar perfis e envelopes como funções puras; manter relógio e máquina de estados separados da geometria. Usar os seis parâmetros B e `m/breath` como contrato de pose. Eventos devem ter política explícita de conclusão e cancelamento. A captura de áudio e TTS serão entradas independentes. Os GIF/WebP são referências, não o motor de animação. A Fase D consolidará a arquitetura, validará o comportamento em Qt Quick/QML e tratará a integração nativa; não está implementada aqui.
