import { Routes } from '@angular/router';
import { AuthGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'login',
    pathMatch: 'full'
  },

  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard/dashboard')
        .then(m => m.Dashboard)
    , canActivate: [AuthGuard]
  },

  {
    path: 'emails',
    loadComponent: () =>
      import('./features/emails/emails/emails')
        .then(m => m.Emails)
    , canActivate: [AuthGuard]
  },

  {
    path: 'tasks',
    loadComponent: () =>
      import('./features/tasks/tasks/tasks')
        .then(m => m.Tasks)
    , canActivate: [AuthGuard]
  },

  {
    path: 'drafts',
    loadComponent: () =>
      import('./features/drafts/drafts/drafts')
        .then(m => m.Drafts)
    , canActivate: [AuthGuard]
  },

  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/settings/settings')
        .then(m => m.Settings)
    , canActivate: [AuthGuard]
  },

  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login')
        .then(m => m.Login)
  },

  {
    path: '**',
    redirectTo: 'dashboard'
  }
];