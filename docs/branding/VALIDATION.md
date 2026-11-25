# Relatório de validação — Fase D

## Resultado executado

- SHA-256: 16/16 arquivos do ZIP A, 35/35 do ZIP A+B e 60/60 do ZIP A+B+C correspondem aos recursos mapeados no pacote final, byte a byte. Os conjuntos são cumulativos (60 arquivos únicos). Originais não foram sobrescritos; foram reorganizados. `approved-manifest.json` é o mapa verificável.
- `test-phase-b.js`: 1.200 caminhos fechados e finitos, endpoints, ciclos, resposta de áudio; passou.
- `test-phase-c.js`: 2.505 caminhos fechados e finitos, 81 pares de interpolação, assinaturas de movimento, endpoints neutros, repetição e destinos; passou.
- `test-exports.py` e `test-exports-c.py`: dimensões, frames, duração, loops, transparência, neutralidade conforme fase; passaram. `test-final.py` decodificou todos os 24 arquivos animados, 320×320, verificando o alfa de canto de todos os frames WebP e o fundo Void de todos os frames GIF. Não implica comparação pixel a pixel com o raster original da marca, apenas preservação das exportações aprovadas.
- Chromium: os testes de fluxos e regressão A/B/C foram executados contra o HTML final em diretório temporário. Sete fluxos C, fluxo completo A+B, espera indefinida, confirmação/recusa, retorno anterior/hold/outro, repetição e interrupções, scrub, dimensão, fundo, modo de áudio manual/auto, stream virtual e tratamento de permissão negada passaram. Novos controles de posição e inspeção passaram. Sem erros de página observados.
- Ausência de rotação global: revisão dos módulos originais, que deformam coordenadas em base diagonal constante; sem animação angular. Coordenadas dos pontos de controle finitas e dentro do viewBox nas amostras testadas. Não é prova de todos os valores possíveis ou de continuidade C1.
- Recursos estáticos: XML de todos os SVGs parseável; PNGs de logotipo com RGBA (0–255); 9 dimensões de ícones conferidas com alfa; inspeção visual da prancha `assets/branding/previews/static-applications.png`. No favicon 16 px e tray, a folga do anel perde detalhe; o símbolo fica mais identificável a partir de 32 px. Não foi executado teste formal de reconhecimento de marca ou em monitor físico.

## Contraste

Razões aproximadas calculadas por luminância relativa sRGB: Starlight/Void 16,86:1, Starlight/Nebula 14,30:1, Starlight/branco 1,17:1, Starlight/Starlight 1:1. Nova/Void 5,61:1 e o violeta ativo #893DB7/Void 3,21:1. Valores de cores sólidas, não um certificado de acessibilidade do gradiente/arte. A prancha confirma baixa legibilidade do núcleo sobre Starlight. Proposta: uma superfície local Void/Nebula para o Overlay em fundo claro; aplicações estáticas podem usar variantes light/mono. Nenhum estado foi recolorido.

## Limitações e decisões

- Wordmark e slogan traçados da prancha raster (isocontornos subpixel, polígonos editáveis); não há curvas tipográficas originais, identificação exata da fonte ou reprodução pixel a pixel. Não substituir os vetores aprovados do símbolo e do Core. Ícones foram renderizados a partir do SVG aprovado, sem simplificação geométrica.
- O HTML final mantém o runtime aprovado; acrescenta posição inferior direita dentro da área de teste e inspector. Modo reduzido não implementado; documentado como proposta de acessibilidade futura. Não é simulação de compositor desktop.
- Os testes de navegador foram em Chromium com `set_content`, relógio virtual nos fluxos C e stream sintético local no teste de microfone. Não testam permissões reais de navegador, hardware, TTS físico, outros navegadores ou integração native. A animação filtra amplitude, não analisa semântica da voz.
- Continuidade C0; velocidade instantânea e fase exata de loops não restauradas ao interromper/retornar (comportamento aprovado). Modo QML, compatibilidade de máscaras, performance Linux, Wayland/X11, DPR e integração com Core Engine pendentes. Não existe implementação da aplicação definitiva.
- Sem licença de publicação escolhida. Ver LICENSES.md.

## Reprodução e logs

`tools/motion-lab/tests/run-regression.py` e `test-final.py`. Logs brutos em `validation-logs/`. A verificação de ZIP deve ser executada após o empacotamento (`python -m zipfile -t ...`); integridade SHA-256 permite detectar alterações posteriores.
