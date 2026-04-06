import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://riukjenrqfdsbvsessmk.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJpdWtqZW5ycWZkc2J2c2Vzc21rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4OTAyMzgsImV4cCI6MjA5MDQ2NjIzOH0.3gndRl_qYo7BERiDQvb7V0PSCnsaNw2DZ93Vp-uCpPA';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
