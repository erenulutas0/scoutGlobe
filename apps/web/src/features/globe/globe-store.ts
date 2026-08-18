import { create } from "zustand";

export interface CountryMeta {
  code: string;
  name: string;
  nameTr: string;
  lat: number;
  lng: number;
}

interface GlobeState {
  /** Numeric ISO 3166-1 id (world-atlas topology key) of the hovered country. */
  hoveredId: string | null;
  /** Numeric ISO 3166-1 id of the selected (clicked) country. */
  selectedId: string | null;
  setHovered: (id: string | null) => void;
  setSelected: (id: string | null) => void;
}

export const useGlobeStore = create<GlobeState>((set) => ({
  hoveredId: null,
  selectedId: null,
  setHovered: (hoveredId) => set({ hoveredId }),
  setSelected: (selectedId) => set({ selectedId }),
}));
