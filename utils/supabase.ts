import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://dhlxkzvgdkytcyguxvxr.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRobHhrenZnZGt5dGN5Z3V4dnhyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM1ODM0NzYsImV4cCI6MjA4OTE1OTQ3Nn0.GQybPpaAFMiePAneZhoVejM0SLVEPYW7W5gLeOiUY1A';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
