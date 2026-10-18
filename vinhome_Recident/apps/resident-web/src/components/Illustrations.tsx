export function Neighborhood() {
  return (
    <svg
      className="neighborhood"
      viewBox="0 0 310 210"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="240" cy="43" r="26" fill="#FFE0BE" />
      <path
        d="M20 173C67 151 97 165 136 158c61-12 110-18 165 8v44H20Z"
        fill="#FFC0A6"
      />
      <path d="M158 55h56v127h-56z" fill="#FFF8EC" />
      <path d="M214 55h16v127h-16z" fill="#FFD9C4" />
      <path d="m152 56 38-21 40 21z" fill="#F1B89E" />
      <path d="M82 88h63v97H82z" fill="#FFF" />
      <path d="M145 88h14v97h-14z" fill="#FFDCCB" />
      <path d="m76 89 34-23 49 23z" fill="#FFE5D3" />
      {[0, 1, 2, 3].map((row) =>
        [0, 1].map((col) => (
          <rect
            key={`a${row}${col}`}
            x={170 + col * 21}
            y={68 + row * 24}
            width="10"
            height="14"
            rx="2"
            fill="#91BCBD"
          />
        )),
      )}
      {[0, 1, 2].map((row) =>
        [0, 1, 2].map((col) => (
          <rect
            key={`b${row}${col}`}
            x={91 + col * 17}
            y={101 + row * 22}
            width="8"
            height="12"
            rx="2"
            fill="#A7CACC"
          />
        )),
      )}
      <path d="M109 165h15v20h-15z" fill="#719EAA" />
      <path d="M180 165h14v17h-14z" fill="#719EAA" />
      <path
        d="M51 139v44m195-49v49"
        stroke="#729785"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <ellipse cx="51" cy="133" rx="19" ry="29" fill="#86B6A0" />
      <ellipse cx="246" cy="130" rx="21" ry="33" fill="#5F9F8B" />
      <path
        d="M35 185h239"
        stroke="#FFF4E6"
        strokeWidth="7"
        strokeLinecap="round"
      />
      <rect x="236" y="169" width="42" height="5" rx="2" fill="#AD7B60" />
      <path d="M241 173v10m31-10v10" stroke="#AD7B60" strokeWidth="3" />
      <path
        d="M30 77h27m-14-6v13M264 80h14m-7-6v12"
        stroke="#FFE5CF"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="m109 45 7 4 7-4m9 5 7 4 7-4"
        stroke="#C77E70"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function LeafMark() {
  return (
    <svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
      <path
        d="M18 29V17m0 5C8 22 5 15 6 7c9 0 14 5 12 15Zm0-4c0-7 5-11 12-11 0 8-4 13-12 14"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
