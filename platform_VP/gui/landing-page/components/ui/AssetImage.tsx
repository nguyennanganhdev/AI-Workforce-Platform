import type { ImgHTMLAttributes } from "react";

/** Native responsive images; source variants are generated at build preparation. */
export default function AssetImage({
  src = "",
  sizes,
  loading = "lazy",
  ...props
}: ImgHTMLAttributes<HTMLImageElement>) {
  let srcSet: string | undefined;
  if (/\/agent-[a-z-]+(?:-(?:240|480))?\.webp$/.test(src)) {
    const base = src
      .replace(/-(?:240|480)\.webp$/, ".webp")
      .replace(/\.webp$/, "");
    srcSet = `${base}-240.webp 240w, ${base}-480.webp 480w, ${base}.webp 700w`;
  } else if (src.includes("/hero-squad")) {
    const base = src.replace(/(?:-768)?\.webp$/, "");
    srcSet = `${base}-768.webp 768w, ${base}.webp 1254w`;
  }
  const image = (
    <img
      {...props}
      src={src}
      srcSet={srcSet}
      sizes={sizes || (props.width ? `${props.width}px` : undefined)}
      loading={loading}
      decoding="async"
    />
  );
  if (src.includes('/hero-squad')) {
    const base = src.replace(/(?:-768)?\.webp$/, '');
    return <picture><source type="image/avif" srcSet={`${base}-768.avif 768w, ${base}.avif 1254w`} sizes={sizes} />{image}</picture>;
  }
  return image;
}
