# Kosmos — Motion Design / Phase A

Protótipo para aprovação, limitado a Standby, Awakening e Sleeping. Não inclui os estados da Fase B/C, captura de microfone, síntese de áudio nem integração com PySide6.

## Uso

Abra `previews/playground.html` diretamente em um navegador. Não requer servidor, internet, fontes externas ou dependências. Ative/desative o Core, inspecione o morphing, ajuste dimensões e altere o fundo. O estado Core é apenas uma pose estática de destino.

## Geometria e decisões

- Reconstrução vetorial manual a partir da prancha aprovada (referência principal); imagens individuais serviram de apoio. Não existia vetor original: contornos Bézier e círculos foram aproximados, não são uma reprodução pixel a pixel. Nenhum frame gerado por IA.
- ViewBox 320 × 320, inclinação estável, centros ópticos das caixas orbitais alinhados, uma escala comum. O centro do círculo branco se desloca internamente alguns pixels para respeitar as poses aprovadas; não há translação do conjunto.
- Uma curva orbital fechada com oito segmentos cúbicos correspondentes. Interpolação de todos os pontos de controle; sem rotação, crossfade ou troca de imagens. Raio exterior diminui e raio interior chega a zero. Máscara de recorte acompanha a órbita e preserva o espaço negativo. Sleeping usa a função inversa.
- Cor Starlight oficial e gradientes aproximados da prancha aprovada, com Nova no Core. O violeta #893DB7 e os tons #AD70BD/#B16EB9 preservam as nuances já presentes na prancha, sem constituir uma nova paleta institucional.
- Standby: 3200 ms, respiração de até 0,8% no anel branco, loop contínuo. Awakening/Sleeping: 1200 ms, easing quintic smoothstep, one-shot; pausa final de 420 ms no arquivo de apresentação. GIFs em fundo Void, cerca de 30 fps com quantização temporal do formato; WebPs lossless com alfa. GIFs e WebPs 320 × 320. Para reatividade futura, não usar estes vídeos como fonte principal.
- A versão clara serve à avaliação de contraste, não a uma adaptação cromática da marca; Starlight tem baixo contraste sobre Starlight. Tamanho mínimo utilizável precisa de avaliação visual na Fase D; nenhum ícone reduzido foi redesenhado.

## Arquivos

`core/static/`: poses vetoriais editáveis e PNGs transparentes.
`animations/`: GIFs de apresentação e WebPs animados transparentes.
`previews/playground.html`: demonstração autônoma.
`source/geometry.js`: geometria, interpolação, cores e temporização compartilhadas.
`source/render-frames.js`: exportação das poses e sequência SVG (Node.js).
`source/export.py`: rasterização por Chromium e exportação (Python, Pillow e Playwright).
`source/playground-template.html`: template da demonstração; substitua o comentário `/* GEOMETRY_SOURCE */` pelo conteúdo de `geometry.js` para reconstruir a página.

## Reproduzir exportação

Com Node.js, Python 3, Chromium instalado e disponível no PATH:

```sh
pip install pillow playwright
python source/export.py
```

## Integração futura QML

Portar os vetores de coordenadas A/B e whiteA/whiteB para um componente Qt Quick. Interpolar com uma propriedade real `morph` de 0 a 1 e `breath` de 0 a 1. Usar easing equivalente à função `ease`. Renderizar a órbita com curvas cúbicas, o núcleo com uma forma de preenchimento even-odd e recorte/máscara para a folga. A implementação QML e desempenho em Linux ainda não foram testados. O SVG usa máscara de luminância; validar suporte do renderizador escolhido, ou implementar recorte diretamente em QML.

## Validação prevista

Aprovar a silhueta dos extremos, a continuidade do morphing e a sutileza do repouso antes de desenvolver os outros estados.
