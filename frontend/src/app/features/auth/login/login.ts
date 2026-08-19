import { Component } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-login',
  imports: [MatIconModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  readonly loginUrl = `${environment.apiUrl}/auth/google/login`;
}
