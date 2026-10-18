import { RouteObject } from 'react-router-dom';
import { Home } from './pages/Home';
import { HowItWorks } from './pages/HowItWorks';
import { SkillAtlas } from './pages/SkillAtlas';
import { Platform } from './pages/Platform';
import { TracePage } from './pages/TracePage';
import { NotFound } from './pages/NotFound';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Home />,
  },
  {
    path: '/how-it-works',
    element: <HowItWorks />,
  },
  {
    path: '/skills',
    element: <SkillAtlas />,
  },
  {
    path: '/platform',
    element: <Platform />,
  },
  {
    path: '/platform/:conversationId',
    element: <Platform />,
  },
  {
    path: '/platform/:conversationId/trace/:runId',
    element: <TracePage />,
  },
  {
    path: '*',
    element: <NotFound />,
  },
];
