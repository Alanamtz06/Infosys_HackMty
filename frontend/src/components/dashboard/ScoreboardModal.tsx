interface Props {
  open: boolean;
  onClose: () => void;
  intelligentEarnings: number;
  noviceEarnings: number;
}

export function ScoreboardModal({ open, onClose, intelligentEarnings, noviceEarnings }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/60">
      <div className="w-96 rounded-xl bg-neutral-900 p-6 text-neutral-100">
        <h2 className="mb-4 text-lg font-semibold">Marcador Global</h2>
        <div className="mb-2 flex justify-between">
          <span>Agente Inteligente</span>
          <span className="font-mono text-emerald-400">${intelligentEarnings.toFixed(2)}</span>
        </div>
        <div className="mb-4 flex justify-between">
          <span>Agente Novato</span>
          <span className="font-mono text-neutral-400">${noviceEarnings.toFixed(2)}</span>
        </div>
        <button onClick={onClose} className="w-full rounded-md bg-neutral-800 py-2 hover:bg-neutral-700">
          Cerrar
        </button>
      </div>
    </div>
  );
}
