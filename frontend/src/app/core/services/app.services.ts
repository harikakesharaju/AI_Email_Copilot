import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {

  private api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  get<T>(url: string) {
    return this.http.get<T>(`${this.api}${url}`, { withCredentials: true });
  }

  post<T>(url: string, body: any) {
    return this.http.post<T>(`${this.api}${url}`, body, { withCredentials: true });
  }

  put<T>(url: string, body: any) {
    return this.http.put<T>(`${this.api}${url}`, body, { withCredentials: true });
  }

  delete<T>(url: string) {
    return this.http.delete<T>(`${this.api}${url}`, { withCredentials: true });
  }

}