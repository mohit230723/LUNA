import React from 'react';
import { useRoutes } from 'react-router-dom';
import { routes } from './routes';

export const AppContent: React.FC = () => {
  const element = useRoutes(routes);
  return element;
};

export const App: React.FC = () => {
  return <AppContent />;
};
