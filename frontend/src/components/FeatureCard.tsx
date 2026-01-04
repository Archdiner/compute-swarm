import React from 'react';

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

export const FeatureCard: React.FC<FeatureCardProps> = ({ icon, title, description }) => {
  return (
    <div className="p-6 rounded-lg border border-zinc-800/60 bg-zinc-900/10 space-y-3 hover:border-zinc-700/60 transition-colors">
      <div className="p-2 bg-zinc-900 w-fit rounded border border-zinc-800 shadow-sm">
        {icon}
      </div>
      <h3 className="font-medium text-white">{title}</h3>
      <p className="text-zinc-500 text-sm leading-relaxed">{description}</p>
    </div>
  );
};

