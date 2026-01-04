import React from 'react';

interface LabelProps {
  children: React.ReactNode;
}

export const Label: React.FC<LabelProps> = ({ children }) => {
  return (
    <label className="block text-[10px] font-bold text-zinc-500 uppercase tracking-[0.15em]">
      {children}
    </label>
  );
};

