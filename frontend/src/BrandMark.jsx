export default function BrandMark({ size = 24, className = '' }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <path d="M16 2.5 27.5 9v14L16 29.5 4.5 23V9L16 2.5Z" fill="currentColor" />
    <path d="m17.4 6.5-7.2 11.2h5.2l-1.1 8 7.6-12.4h-5.1l.6-6.8Z" fill="var(--brand-mark-cutout, white)" />
  </svg>
}
