import React from 'react';

interface FlyingBeeProps {
  className?: string;
  size?: number;
}

export const FlyingBee: React.FC<FlyingBeeProps> = ({ className = '', size = 24 }) => (
  <div className={`relative ${className} animate-float`}>
    <svg 
      width={size} 
      height={size} 
      viewBox="0 0 24 24" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg" 
      className="drop-shadow-[0_0_8px_rgba(251,191,36,0.4)]"
    >
      <path 
        d="M12 17C14.7614 17 17 14.7614 17 12C17 9.23858 14.7614 7 12 7C9.23858 7 7 9.23858 7 12C7 14.7614 9.23858 17 12 17Z" 
        fill="#FBBF24" 
      />
      <path 
        d="M12 7C12 4.23858 9.76142 2 7 2C4.23858 2 2 4.23858 2 7C2 9.76142 4.23858 12 7 12C9.76142 12 12 14.2386 12 17M12 7C12 9.23858 14.2386 12 17 12C19.7614 12 22 9.76142 22 7C22 4.23858 19.7614 2 17 2C14.2386 2 12 4.23858 12 7Z" 
        stroke="#FBBF24" 
        strokeWidth="1.5" 
        strokeLinecap="round" 
      />
      <circle cx="10" cy="11" r="1" fill="black" />
      <circle cx="14" cy="11" r="1" fill="black" />
    </svg>
  </div>
);

