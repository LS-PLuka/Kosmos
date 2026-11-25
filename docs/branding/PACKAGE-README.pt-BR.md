# Kosmos — Branding & Motion Lab / 1.0

Consolidação das fases A, B e C aprovadas, com novos derivados estáticos, documentação e ferramentas da Fase D. Não é a aplicação desktop. Não há implementação Core Engine, QML, automações ou autorização real.

## Início rápido

Abra `tools/motion-lab/index.html` em um navegador moderno. Sem dependências externas. Para acesso ao microfone, se arquivo local não for permitido, execute na raiz do pacote:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Abra `http://localhost:8765/tools/motion-lab/`. Permissão é opcional; selecione modo manual ou simulação para usar sem microfone. Os dois controles novos são inspeção de pose/tempo e posicionamento no canto inferior direito da área de teste, não uma simulação do sistema operacional. Não há modo reduzido implementado (proposta documentada).

## Organização

```
assets/branding/
  logos/        wordmark e variações, SVG + PNG
  symbols/      símbolo institucional aprovado e derivados
  icons/        PNG, tray, favicon, GitHub
  core/         Core, geometria estruturada e amostras
  animations/   12 estados, GIF + WebP originais
  previews/     capturas e referências de movimento
  reference/    prancha aprovada e imagens iniciais
 tools/motion-lab/
  index.html    versão final autônoma
  source/       módulos, exportadores, builders
  tests/        testes originais e consolidados
  history/      HTMLs A/B/C preservados
 docs/branding/
  BRAND-GUIDE.md
  QML-SPEC.md
  OVERLAY-CONTRACT.md
  LICENSES.md
  VALIDATION.md
  history/      documentos e relatório aprovados
 approved-manifest.json  mapa de caminhos e SHA-256 dos 60 arquivos anteriores
```

## Desenvolvimento

Node.js e Python 3 para exportações e testes; instale opcionalmente `python -m pip install pillow playwright opencv-python numpy scipy scikit-image` e Chromium (no PATH ou `python -m playwright install chromium`). Sem dependências para abrir a demonstração. Para reconstruir a versão final e os dados numéricos:

```sh
python tools/motion-lab/source/build-final.py
node tools/motion-lab/source/export-spec.js
python tools/motion-lab/source/export-brand.py
python tools/motion-lab/tests/test-final.py
python tools/motion-lab/tests/run-regression.py
```

Os scripts históricos usam caminhos A–C. O runner monta esses caminhos em diretório temporário, verifica hashes e roda regressões contra o HTML final. Não execute exportadores históricos diretamente na árvore consolidada; para reexportar animações, restaure o layout original usando `approved-manifest.json` (origem = chave, destino = path no pacote), em área temporária. Não sobrescreva ativos aprovados sem revisão. Os HTMLs autônomos incluem os módulos, intencionalmente; a fonte normativa é o JS separado.

Leia `docs/branding/BRAND-GUIDE.md`, `QML-SPEC.md`, `OVERLAY-CONTRACT.md` e `LICENSES.md`. Os GIFs/WebPs são referências para documentação e aprovação. Renderização final será vetorial e reativa em Qt Quick. A licença de publicação e política de marca ainda precisam ser escolhidas pelo mantenedor.
