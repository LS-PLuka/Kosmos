# Overlay — contrato proposto (não implementado)

O Core Engine publica snapshots e eventos por uma interface local, sem dependência do renderer. Em monólito modular Python, um adaptador Qt entrega sinais enfileirados na GUI thread; o domínio não importa QML. O Overlay só representa informação, emite intenção do usuário e faz animação local. Core Engine autoriza/executa ferramentas e mantém as regras de negócio.

```text
VisualSnapshot { revision: int, active: bool,
  state: standby|listening|thinking|executing|speaking|confirmation,
  micAmplitude: float[0,1], ttsAmplitude: float[0,1],
  confirmationId: string|null }
VisualEvent { id: string, revision: int,
  kind: success|notification|warning|error,
  priority: normal|high, repeat: bool,
  after: previous|hold|standby|listening|thinking|executing|speaking|confirmation|core }
VisualCancel { revision: int, eventId: string|null }
ConfirmationIntent { confirmationId: string, decision: approve|decline|cancel }
```

- Snapshot mais recente prevalece; revision monotônica por sessão; entradas de amplitude podem ser atualizadas independentemente em alta frequência sem reiniciar perfil/tempo (separar sinais de amplitude dos de estado). Valores inválidos/clamp e ausência tratadas como zero. Não misturar mic/TTS. `active=false` solicita Sleeping → Standby. Awakening/Sleeping e Core neutro são modos locais derivados, não ordens de negócio.
- Eventos têm ID único e são deduplicados. Prioridade normal respeita evento atual até política explícita do emissor; high pode interromper, partindo da pose exibida. Política simples: nenhum evento visual deve implicitamente autorizar ou cancelar uma confirmação; se há confirmação pendente, o Engine decide adiar o evento ou reapresentar confirmação após o evento. Prioridade é metadado, não cor. O Engine decide destino; `previous` captura último estado estável solicitado e retorna reiniciando seu relógio; `hold` termina neutro. Repetição permitida apenas Warning/Error. Cancelamento por ID invalida timer; cancelamento global substitui fluxo por snapshot atual. Ignore conclusões antigas após nova revisão/evento. A política de prioridade é proposta D, não comportamento existente no Lab.
- Intenções de confirmação só são emitidas por ação explícita, incluindo ID; o Engine verifica correlação, validade, autorização e execução, depois envia novo snapshot. A animação não concede acesso, não possui timeout de aprovação, nem executa ação. Recusa/cancelamento são tratados no Engine. Não expor dados de ferramentas ou conteúdo de áudio ao renderer.
- Opcional `visualEventFinished(id)` para telemetria visual, nunca como precondição para operação. Testes devem garantir duplicação, eventos fora de ordem, interrupção, confirmação vencida, desconexão e zeros de amplitude. Sem rede, filas externas ou dependências de infraestrutura necessárias.
