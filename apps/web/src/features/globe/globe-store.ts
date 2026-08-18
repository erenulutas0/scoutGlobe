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
  /** Drill-down: country -> league -> club. Null means "not opened yet". */
  selectedLeagueId: number | null;
  selectedClubId: number | null;

  setHovered: (id: string | null) => void;
  selectCountry: (id: string | null) => void;
  selectLeague: (id: number | null) => void;
  selectClub: (id: number | null) => void;
  /** Step one level back up the drill-down. */
  goBack: () => void;
}

export const useGlobeStore = create<GlobeState>((set, get) => ({
  hoveredId: null,
  selectedId: null,
  selectedLeagueId: null,
  selectedClubId: null,

  setHovered: (hoveredId) => set({ hoveredId }),
  // Selecting a country resets the levels below it, otherwise the panel would
  // show one country's leagues next to another country's squad.
  selectCountry: (selectedId) =>
    set({ selectedId, selectedLeagueId: null, selectedClubId: null }),
  selectLeague: (selectedLeagueId) => set({ selectedLeagueId, selectedClubId: null }),
  selectClub: (selectedClubId) => set({ selectedClubId }),

  goBack: () => {
    const { selectedClubId, selectedLeagueId } = get();
    if (selectedClubId !== null) return set({ selectedClubId: null });
    if (selectedLeagueId !== null) return set({ selectedLeagueId: null });
    return set({ selectedId: null });
  },
}));
