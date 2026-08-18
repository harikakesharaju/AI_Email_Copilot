import { Injectable } from '@angular/core';
import { CanActivate, Router } from '@angular/router';
import { ApiService } from '../services/api.service';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(private api: ApiService, private router: Router) {}

  canActivate(): Observable<boolean> {
    return this.api.get<any>('/api/me').pipe(
      map(() => true),
      catchError((err) => {
        // On any error (including 401) redirect to login
        this.router.navigate(['/login']);
        return of(false);
      })
    );
  }
}
