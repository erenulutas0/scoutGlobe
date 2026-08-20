import { create } from "zustand";

interface PaletteState {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

/**
 * Whether the search palette is open.
 *
 * A store rather than local state because the two halves are mounted in
 * different places: the dialog and its ⌘K listener live once in the root
 * layout so the shortcut works on every page, while the button that opens it
 * belongs in each page's own header. Mounting the pair per page meant ⌘K did
 * nothing on the player profile, which is exactly where a scout ends up.
 */
export const usePaletteStore = create<PaletteState>((set, get) => ({
  open: false,
  setOpen: (open) => set({ open }),
  toggle: () => set({ open: !get().open }),
}));
