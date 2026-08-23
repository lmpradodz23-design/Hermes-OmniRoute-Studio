import { Codicon } from '@/components/ui/codicon'

import { AGENTS_ROUTE, ARTIFACTS_ROUTE, CRON_ROUTE, MESSAGING_ROUTE, SKILLS_ROUTE, STARMAP_ROUTE } from '../../routes'
import type { SidebarNavItem } from '../../types'

// The sidebar's top navigation rail. Each row points to a REAL destination —
// an action (new-session) or an existing route/overlay that renders a working
// view — never a placeholder. New rows belong here only once their destination
// exists. Labels come from i18n `sidebar.nav[id]`; add the matching key when
// you add a row.
//
// Agents sits right below New session: the mission's Workspace U1 wants agents
// reachable from the primary surface, not buried in a separate screen. It
// navigates to AGENTS_ROUTE, which the router already mounts (the AgentsView),
// so it is a live destination, not a dead button.
export const SIDEBAR_NAV: SidebarNavItem[] = [
  {
    id: 'new-session',
    label: '',
    icon: props => <Codicon name="robot" {...props} />,
    action: 'new-session',
    keybindActionId: 'session.new'
  },
  {
    id: 'agents',
    label: '',
    icon: props => <Codicon name="organization" {...props} />,
    route: AGENTS_ROUTE,
    keybindActionId: 'nav.agents'
  },
  {
    id: 'skills',
    label: '',
    icon: props => <Codicon name="symbol-misc" {...props} />,
    route: SKILLS_ROUTE,
    keybindActionId: 'nav.skills'
  },
  {
    id: 'messaging',
    label: '',
    icon: props => <Codicon name="comment" {...props} />,
    route: MESSAGING_ROUTE,
    keybindActionId: 'nav.messaging'
  },
  {
    id: 'artifacts',
    label: '',
    icon: props => <Codicon name="files" {...props} />,
    route: ARTIFACTS_ROUTE,
    keybindActionId: 'nav.artifacts'
  },
  {
    id: 'cron',
    label: '',
    icon: props => <Codicon name="watch" {...props} />,
    route: CRON_ROUTE,
    keybindActionId: 'nav.cron'
  },
  {
    // Memory surface: the starmap is where remembered context/skills live
    // (mission §17/§18). STARMAP_ROUTE already mounts the view — live target.
    id: 'starmap',
    label: '',
    icon: props => <Codicon name="sparkle" {...props} />,
    route: STARMAP_ROUTE
  }
]
