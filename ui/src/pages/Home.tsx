import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';
import { Divider } from '../components/ui/Divider';
import { Hero } from '../components/home/Hero';
import { FeatureGrid } from '../components/home/FeatureGrid';
import { UseCases } from '../components/home/UseCases';
import { FlowSteps } from '../components/home/FlowSteps';
import { Manifesto } from '../components/home/Manifesto';
import { UnderTheHood } from '../components/home/UnderTheHood';
import { FinalCta } from '../components/home/FinalCta';

export const Home: React.FC = () => {
  useEffect(() => {
    document.title = 'LUNA OS';
  }, []);

  return (
    <PageShell>
      <Hero />
      <Divider />
      <FeatureGrid />
      <Divider />
      <UseCases />
      <Divider />
      <FlowSteps />
      <Divider />
      <Manifesto />
      <Divider />
      <UnderTheHood />
      <Divider />
      <FinalCta />
    </PageShell>
  );
};
