import utep from "./utep.png";

// The logo: UTEP's pickaxe mark in UTEP Orange, and the name beside it.
// Imported (not in public/) so the build bundles it: the Docker image does not copy public/.
export default function Brand() {
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- a 5 KB logo, already at its size: nothing to optimise */}
      <img src={utep.src} width={utep.width} height={utep.height} alt="" />
      <span>cyber<span className="ai">AI</span></span>
    </>
  );
}
