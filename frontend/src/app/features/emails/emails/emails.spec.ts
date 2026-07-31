import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Emails } from './emails';

describe('Emails', () => {
  let component: Emails;
  let fixture: ComponentFixture<Emails>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Emails],
    }).compileComponents();

    fixture = TestBed.createComponent(Emails);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
