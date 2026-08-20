-- Hominsu VR Studio initial schema.
-- Apply with: supabase db push

create type public.content_type as enum ('VOD', 'LIVE_360', 'SHORT_FORM');
create type public.device_status as enum ('ONLINE', 'OFFLINE', 'MAINTENANCE');
create type public.transaction_type as enum ('RECHARGE', 'SPEND', 'BONUS');

create table public.users (
    id uuid primary key,
    email varchar(255) not null unique,
    name varchar(255) not null,
    provider varchar(32) not null default 'local',
    hashed_password varchar(255),
    points_balance integer not null default 0,
    created_at timestamptz default now()
);

create index ix_users_email on public.users (email);

create table public.contents (
    id uuid primary key,
    title varchar(500) not null,
    type public.content_type not null default 'VOD',
    stream_key varchar(255) unique,
    media_url varchar(1000),
    price_points integer not null default 0,
    is_live boolean not null default false,
    viewer_count integer not null default 0,
    created_at timestamptz default now()
);

create index ix_contents_stream_key on public.contents (stream_key);

create table public.devices (
    id varchar(64) primary key,
    model varchar(255) not null default 'Unknown',
    status public.device_status not null default 'OFFLINE',
    battery_level double precision not null default 0.0,
    ip_address varchar(64),
    firmware_version varchar(64),
    current_content_id uuid references public.contents(id),
    last_heartbeat timestamptz
);

create table public.point_transactions (
    id uuid primary key,
    user_id uuid not null references public.users(id),
    amount integer not null,
    type public.transaction_type not null,
    description varchar(500),
    created_at timestamptz default now()
);

create index ix_point_transactions_user_id
    on public.point_transactions (user_id);
