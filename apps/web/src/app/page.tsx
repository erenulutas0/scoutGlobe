import { GlobeScene } from "@/features/globe/GlobeScene";
import { TopBar } from "@/features/shell/TopBar";

export default function HomePage() {
  return (
    <main className="starfield relative h-dvh w-full overflow-hidden">
      <TopBar />
      <GlobeScene />
    </main>
  );
}
