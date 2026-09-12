interface Props {
  open: boolean;
  onClose: () => void;
  intelligentEarnings: number;
  noviceEarnings: number;
}

export function ScoreboardModal({ open, onClose, intelligentEarnings, noviceEarnings }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-ink/40 backdrop-blur-sm animate-fade-in">
      <div className="animate-pop-in relative w-96 overflow-hidden rounded-xl border border-dust bg-paper p-6 text-ink shadow-xl">
        <span className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-plum via-blush to-dust" />
        <h2 className="mb-4 text-lg font-semibold tracking-tight">Global Scoreboard</h2>
        <div className="mb-2 flex items-center justify-between rounded-lg bg-blush/25 px-3 py-2">
          <span className="text-charcoal">Smart Agent</span>
          <span className="font-mono tabular-nums text-plum">${intelligentEarnings.toFixed(2)}</span>
        </div>
        <div className="mb-4 flex items-center justify-between rounded-lg bg-dust/25 px-3 py-2">
          <span className="text-charcoal">Novice Agent</span>
          <span className="font-mono tabular-nums text-charcoal/70">${noviceEarnings.toFixed(2)}</span>
        </div>
        <button
          onClick={onClose}
          className="w-full rounded-md border border-dust bg-white py-2 text-ink transition duration-150 ease-out hover:border-plum/30 hover:bg-dust/30 active:scale-95"
        >
          Close
        </button>
      </div>
    </div>
  );
}
