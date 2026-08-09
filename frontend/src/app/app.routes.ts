import { Routes } from '@angular/router';

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
  },

  {
    path: 'emails',
    loadComponent: () =>
      import('./features/emails/emails/emails')
        .then(m => m.Emails)
  },

  {
    path: 'tasks',
    loadComponent: () =>
      import('./features/tasks/tasks/tasks')
        .then(m => m.Tasks)
  },

  {
    path: 'drafts',
    loadComponent: () =>
      import('./features/drafts/drafts/drafts')
        .then(m => m.Drafts)
  },

  {
    path: 'settings',
    loadComponent: () =>
      import('./features/settings/settings/settings')
        .then(m => m.Settings)
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