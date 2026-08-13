create function public.handle_new_user() returns trigger as $$
begin
  insert into public.profiles (id, org_id, email, role)
  values (new.id, (new.raw_user_meta_data->>'org_id')::uuid, new.email, 'member');
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
