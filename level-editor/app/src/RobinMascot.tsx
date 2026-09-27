import { createEffect, createSignal, onCleanup } from "solid-js";
import bored from "./assets/robin-bored.avif";
import boredRandom from "./assets/robin-bored-random.avif";
import toDance from "./assets/robin-to-dance.avif";
import fromDance from "./assets/robin-from-dance.avif";
import dancing from "./assets/robin-dancing.avif";
import still from "./assets/robin-still.png";
import animation from "./assets/robin-animation.json";

const images = {
  bored,
  "bored-random": boredRandom,
  "to-dance": toDance,
  "from-dance": fromDance,
  dancing,
  still,
};
export default function RobinMascot() {
  const [hovered, setHovered] = createSignal(false);
  const [focused, setFocused] = createSignal(false);
  const [phase, setPhase] = createSignal<keyof typeof images>("bored");
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const [reducedMotion, setReducedMotion] = createSignal(motion.matches);
  const updateMotion = () => setReducedMotion(motion.matches);
  motion.addEventListener("change", updateMotion);
  onCleanup(() => motion.removeEventListener("change", updateMotion));
  createEffect(
    () => ({ dancing: hovered() || focused(), reduced: reducedMotion() }),
    ({ dancing, reduced }) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const schedule = () => {
        // Same random-start probability as the game: 1/250 each 25 Hz tick.
        const ticks = Math.max(1, Math.ceil(Math.log(1 - Math.random()) / Math.log(249 / 250)));
        timer = setTimeout(() => {
          setPhase("bored-random");
          timer = setTimeout(() => {
            setPhase("bored");
            schedule();
          }, animation["robin-bored-random"]);
        }, ticks * 40);
      };
      if (reduced) setPhase("still");
      else if (dancing) {
        setPhase("to-dance");
        timer = setTimeout(() => setPhase("dancing"), animation["robin-to-dance"]);
      } else if (phase() === "dancing" || phase() === "to-dance") {
        setPhase("from-dance");
        timer = setTimeout(() => {
          setPhase("bored");
          schedule();
        }, animation["robin-from-dance"]);
      } else {
        setPhase("bored");
        schedule();
      }
      return () => clearTimeout(timer);
    },
  );
  // Preserve the exported hotspot at the header baseline at one scale for every pose.
  const scale = 0.8;
  return (
    <span
      class="robin-mascot"
      tabindex={0}
      role="img"
      aria-label="Robin Hood. Hover or focus to make him dance."
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
    >
      <img
        class={`robin-frame robin-${phase()}`}
        src={images[phase()]}
        alt=""
        style={{
          width: `${animation.canvas.width * scale}px`,
          height: `${animation.canvas.height * scale}px`,
          left: `calc(50% - ${animation.canvas.anchorX * scale}px)`,
          top: `calc(100% + 6px - ${animation.canvas.anchorY * scale}px)`,
        }}
      />
    </span>
  );
}
