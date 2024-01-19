--
-- PostgreSQL database dump
--

-- Dumped from database version 14.4 (Debian 14.4-1.pgdg110+1)
-- Dumped by pg_dump version 14.4 (Debian 14.4-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


ALTER TABLE public.auth_group OWNER TO fda;

--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_group_id_seq OWNER TO fda;

--
-- Name: auth_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_group_id_seq OWNED BY public.auth_group.id;


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_group_permissions OWNER TO fda;

--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_group_permissions_id_seq OWNER TO fda;

--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_group_permissions_id_seq OWNED BY public.auth_group_permissions.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


ALTER TABLE public.auth_permission OWNER TO fda;

--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_permission_id_seq OWNER TO fda;

--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_permission_id_seq OWNED BY public.auth_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


ALTER TABLE public.auth_user OWNER TO fda;

--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_user_groups (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


ALTER TABLE public.auth_user_groups OWNER TO fda;

--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_groups_id_seq OWNER TO fda;

--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_user_groups_id_seq OWNED BY public.auth_user_groups.id;


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_id_seq OWNER TO fda;

--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.auth_user_user_permissions (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


ALTER TABLE public.auth_user_user_permissions OWNER TO fda;

--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.auth_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.auth_user_user_permissions_id_seq OWNER TO fda;

--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.auth_user_user_permissions_id_seq OWNED BY public.auth_user_user_permissions.id;


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id integer NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


ALTER TABLE public.django_admin_log OWNER TO fda;

--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.django_admin_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_admin_log_id_seq OWNER TO fda;

--
-- Name: django_admin_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.django_admin_log_id_seq OWNED BY public.django_admin_log.id;


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


ALTER TABLE public.django_content_type OWNER TO fda;

--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.django_content_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_content_type_id_seq OWNER TO fda;

--
-- Name: django_content_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.django_content_type_id_seq OWNED BY public.django_content_type.id;


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


ALTER TABLE public.django_migrations OWNER TO fda;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.django_migrations_id_seq OWNER TO fda;

--
-- Name: django_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.django_migrations_id_seq OWNED BY public.django_migrations.id;


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


ALTER TABLE public.django_session OWNER TO fda;

--
-- Name: fda_ecsfield; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfield (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    md5_hash character varying(32) NOT NULL,
    name character varying(50) NOT NULL,
    flat_name character varying(128) NOT NULL,
    is_ecs boolean NOT NULL,
    description character varying(5000) NOT NULL,
    required boolean,
    short character varying(500) NOT NULL,
    example character varying(500) NOT NULL,
    index boolean,
    format character varying(200) NOT NULL,
    input_format character varying(20) NOT NULL,
    output_format character varying(200) NOT NULL,
    output_precision character varying(200) NOT NULL,
    pattern character varying(200) NOT NULL,
    expected_values character varying(200)[],
    "normalize" character varying(20)[],
    beta character varying(200) NOT NULL,
    doc_values boolean,
    object_type character varying(200) NOT NULL,
    ignore_above integer,
    scaling_factor double precision,
    custom_comment character varying(500) NOT NULL,
    custom_help character varying(500) NOT NULL,
    custom_description character varying(5000) NOT NULL,
    custom_example character varying(500) NOT NULL,
    created_by_id integer NOT NULL,
    ecs_fieldset_id uuid NOT NULL,
    level_id uuid NOT NULL,
    type_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_ecsfield OWNER TO fda;

--
-- Name: fda_ecsfieldallowedvalues; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfieldallowedvalues (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    md5_hash character varying(32) NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(5000) NOT NULL,
    expected_event_types character varying(20)[],
    created_by_id integer NOT NULL,
    ecs_field_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_ecsfieldallowedvalues OWNER TO fda;

--
-- Name: fda_ecsfieldlevel; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfieldlevel (
    id uuid NOT NULL,
    name character varying(20) NOT NULL,
    is_ecs boolean NOT NULL
);


ALTER TABLE public.fda_ecsfieldlevel OWNER TO fda;

--
-- Name: fda_ecsfieldset; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfieldset (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    md5_hash character varying(32) NOT NULL,
    name character varying(50) NOT NULL,
    is_ecs boolean NOT NULL,
    root boolean NOT NULL,
    title character varying(50) NOT NULL,
    description character varying(5000) NOT NULL,
    comment character varying(5000) NOT NULL,
    short character varying(500) NOT NULL,
    short_override character varying(5000) NOT NULL,
    beta character varying(5000) NOT NULL,
    footnote character varying(5000) NOT NULL,
    custom_comment character varying(5000) NOT NULL,
    custom_description character varying(5000) NOT NULL,
    created_by_id integer NOT NULL,
    ecs_version_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_ecsfieldset OWNER TO fda;

--
-- Name: fda_ecsfieldsetreused; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfieldsetreused (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    md5_hash character varying(32) NOT NULL,
    is_ecs boolean NOT NULL,
    reused_as character varying(50) NOT NULL,
    top_level boolean NOT NULL,
    beta character varying(200) NOT NULL,
    short_override character varying(200) NOT NULL,
    created_by_id integer NOT NULL,
    ecs_fieldset_id uuid NOT NULL,
    ecs_reused_at_fieldset_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_ecsfieldsetreused OWNER TO fda;

--
-- Name: fda_ecsfieldtype; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsfieldtype (
    id uuid NOT NULL,
    name character varying(200) NOT NULL,
    is_ecs boolean NOT NULL
);


ALTER TABLE public.fda_ecsfieldtype OWNER TO fda;

--
-- Name: fda_ecsmultifield; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsmultifield (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    md5_hash character varying(32) NOT NULL,
    is_ecs boolean NOT NULL,
    name character varying(200) NOT NULL,
    created_by_id integer NOT NULL,
    ecs_version_id uuid NOT NULL,
    type_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_ecsmultifield OWNER TO fda;

--
-- Name: fda_ecsmultifield_ecs_fields; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsmultifield_ecs_fields (
    id bigint NOT NULL,
    ecsmultifield_id uuid NOT NULL,
    ecsfield_id uuid NOT NULL
);


ALTER TABLE public.fda_ecsmultifield_ecs_fields OWNER TO fda;

--
-- Name: fda_ecsmultifield_ecs_fields_id_seq; Type: SEQUENCE; Schema: public; Owner: fda
--

CREATE SEQUENCE public.fda_ecsmultifield_ecs_fields_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.fda_ecsmultifield_ecs_fields_id_seq OWNER TO fda;

--
-- Name: fda_ecsmultifield_ecs_fields_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fda
--

ALTER SEQUENCE public.fda_ecsmultifield_ecs_fields_id_seq OWNED BY public.fda_ecsmultifield_ecs_fields.id;


--
-- Name: fda_ecsversion; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_ecsversion (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    version_major integer,
    version_minor integer,
    created_by_id integer NOT NULL,
    updated_by_id integer,
    CONSTRAINT fda_ecsversion_version_major_check CHECK ((version_major >= 0)),
    CONSTRAINT fda_ecsversion_version_minor_check CHECK ((version_minor >= 0))
);


ALTER TABLE public.fda_ecsversion OWNER TO fda;

--
-- Name: fda_exampleevent; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_exampleevent (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    is_custom boolean NOT NULL,
    name character varying(128) NOT NULL,
    document text NOT NULL,
    created_by_id integer NOT NULL,
    log_class_id uuid NOT NULL,
    log_source_id uuid,
    updated_by_id integer
);


ALTER TABLE public.fda_exampleevent OWNER TO fda;

--
-- Name: fda_grokpattern; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_grokpattern (
    id character varying(128) NOT NULL,
    type character varying(128) NOT NULL,
    pattern text NOT NULL,
    category_id character varying(128) NOT NULL
);


ALTER TABLE public.fda_grokpattern OWNER TO fda;

--
-- Name: fda_grokpatterncategory; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_grokpatterncategory (
    id character varying(128) NOT NULL,
    type character varying(128) NOT NULL
);


ALTER TABLE public.fda_grokpatterncategory OWNER TO fda;

--
-- Name: fda_logclass; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_logclass (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    name character varying(128) NOT NULL,
    description text NOT NULL,
    contact_person character varying(256) NOT NULL,
    created_by_id integer NOT NULL,
    log_class_status_id uuid NOT NULL,
    release_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_logclass OWNER TO fda;

--
-- Name: fda_logclassmapping; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_logclassmapping (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    created_by_id integer NOT NULL,
    log_class_id uuid NOT NULL,
    updated_by_id integer,
    output_keys character varying(200)[]
);


ALTER TABLE public.fda_logclassmapping OWNER TO fda;

--
-- Name: fda_logclassstatus; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_logclassstatus (
    id uuid NOT NULL,
    name character varying(128) NOT NULL
);


ALTER TABLE public.fda_logclassstatus OWNER TO fda;

--
-- Name: fda_logsource; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_logsource (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    parameters jsonb NOT NULL,
    created_by_id integer NOT NULL,
    log_class_id uuid NOT NULL,
    updated_by_id integer
);


ALTER TABLE public.fda_logsource OWNER TO fda;

--
-- Name: fda_logtarget; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_logtarget (
    id character varying(128) NOT NULL,
    required_fields character varying(50)[] NOT NULL
);


ALTER TABLE public.fda_logtarget OWNER TO fda;

--
-- Name: fda_mappingfunction; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_mappingfunction (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    processor_type character varying(128) NOT NULL,
    configuration jsonb NOT NULL,
    "position" integer NOT NULL,
    source_field character varying(128) NOT NULL,
    created_by_id integer NOT NULL,
    logclass_mapping_id uuid NOT NULL,
    updated_by_id integer,
    parent_function_id uuid,
    CONSTRAINT fda_mappingfunction_position_check CHECK (("position" >= 0))
);


ALTER TABLE public.fda_mappingfunction OWNER TO fda;

--
-- Name: fda_parameterdescription; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_parameterdescription (
    id character varying(256) NOT NULL,
    schema character varying(256) NOT NULL,
    type character varying(256) NOT NULL,
    required boolean NOT NULL,
    parameter_name character varying(256) NOT NULL,
    description text NOT NULL
);


ALTER TABLE public.fda_parameterdescription OWNER TO fda;

--
-- Name: fda_release; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_release (
    id uuid NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone,
    version_major integer NOT NULL,
    version_minor integer NOT NULL,
    base_release_id uuid,
    created_by_id integer NOT NULL,
    ecs_version_id uuid NOT NULL,
    release_status_id uuid NOT NULL,
    stage_id character varying(128) NOT NULL,
    updated_by_id integer,
    CONSTRAINT fda_release_version_major_check CHECK ((version_major >= 0)),
    CONSTRAINT fda_release_version_minor_check CHECK ((version_minor >= 0))
);


ALTER TABLE public.fda_release OWNER TO fda;

--
-- Name: fda_releasestatus; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_releasestatus (
    id uuid NOT NULL,
    name character varying(128) NOT NULL
);


ALTER TABLE public.fda_releasestatus OWNER TO fda;

--
-- Name: fda_stage; Type: TABLE; Schema: public; Owner: fda
--

CREATE TABLE public.fda_stage (
    name character varying(128) NOT NULL,
    ordering smallint NOT NULL,
    CONSTRAINT fda_stage_ordering_check CHECK ((ordering >= 0))
);


ALTER TABLE public.fda_stage OWNER TO fda;

--
-- Name: auth_group id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group ALTER COLUMN id SET DEFAULT nextval('public.auth_group_id_seq'::regclass);


--
-- Name: auth_group_permissions id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_group_permissions_id_seq'::regclass);


--
-- Name: auth_permission id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_permission_id_seq'::regclass);


--
-- Name: auth_user id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq'::regclass);


--
-- Name: auth_user_groups id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_groups ALTER COLUMN id SET DEFAULT nextval('public.auth_user_groups_id_seq'::regclass);


--
-- Name: auth_user_user_permissions id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_user_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_user_user_permissions_id_seq'::regclass);


--
-- Name: django_admin_log id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_admin_log ALTER COLUMN id SET DEFAULT nextval('public.django_admin_log_id_seq'::regclass);


--
-- Name: django_content_type id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_content_type ALTER COLUMN id SET DEFAULT nextval('public.django_content_type_id_seq'::regclass);


--
-- Name: django_migrations id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_migrations ALTER COLUMN id SET DEFAULT nextval('public.django_migrations_id_seq'::regclass);


--
-- Name: fda_ecsmultifield_ecs_fields id; Type: DEFAULT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield_ecs_fields ALTER COLUMN id SET DEFAULT nextval('public.fda_ecsmultifield_ecs_fields_id_seq'::regclass);


--
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_group (id, name) FROM stdin;
\.


--
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_group_permissions (id, group_id, permission_id) FROM stdin;
\.


--
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_permission (id, name, content_type_id, codename) FROM stdin;
1	Can add log entry	1	add_logentry
2	Can change log entry	1	change_logentry
3	Can delete log entry	1	delete_logentry
4	Can view log entry	1	view_logentry
5	Can add permission	2	add_permission
6	Can change permission	2	change_permission
7	Can delete permission	2	delete_permission
8	Can view permission	2	view_permission
9	Can add group	3	add_group
10	Can change group	3	change_group
11	Can delete group	3	delete_group
12	Can view group	3	view_group
13	Can add user	4	add_user
14	Can change user	4	change_user
15	Can delete user	4	delete_user
16	Can view user	4	view_user
17	Can add content type	5	add_contenttype
18	Can change content type	5	change_contenttype
19	Can delete content type	5	delete_contenttype
20	Can view content type	5	view_contenttype
21	Can add session	6	add_session
22	Can change session	6	change_session
23	Can delete session	6	delete_session
24	Can view session	6	view_session
25	Can add ECS Field	7	add_ecsfield
26	Can change ECS Field	7	change_ecsfield
27	Can delete ECS Field	7	delete_ecsfield
28	Can view ECS Field	7	view_ecsfield
29	Can add ECS Field Level	8	add_ecsfieldlevel
30	Can change ECS Field Level	8	change_ecsfieldlevel
31	Can delete ECS Field Level	8	delete_ecsfieldlevel
32	Can view ECS Field Level	8	view_ecsfieldlevel
33	Can add ECS Field Type	9	add_ecsfieldtype
34	Can change ECS Field Type	9	change_ecsfieldtype
35	Can delete ECS Field Type	9	delete_ecsfieldtype
36	Can view ECS Field Type	9	view_ecsfieldtype
37	Can add ECS Version	10	add_ecsversion
38	Can change ECS Version	10	change_ecsversion
39	Can delete ECS Version	10	delete_ecsversion
40	Can view ECS Version	10	view_ecsversion
41	Can add log class	11	add_logclass
42	Can change log class	11	change_logclass
43	Can delete log class	11	delete_logclass
44	Can view log class	11	view_logclass
45	Can add log class mapping	12	add_logclassmapping
46	Can change log class mapping	12	change_logclassmapping
47	Can delete log class mapping	12	delete_logclassmapping
48	Can view log class mapping	12	view_logclassmapping
49	Can add log class status	13	add_logclassstatus
50	Can change log class status	13	change_logclassstatus
51	Can delete log class status	13	delete_logclassstatus
52	Can view log class status	13	view_logclassstatus
53	Can add log target	14	add_logtarget
54	Can change log target	14	change_logtarget
55	Can delete log target	14	delete_logtarget
56	Can view log target	14	view_logtarget
57	Can add mapping function	15	add_mappingfunction
58	Can change mapping function	15	change_mappingfunction
59	Can delete mapping function	15	delete_mappingfunction
60	Can view mapping function	15	view_mappingfunction
61	Can add parameter description	16	add_parameterdescription
62	Can change parameter description	16	change_parameterdescription
63	Can delete parameter description	16	delete_parameterdescription
64	Can view parameter description	16	view_parameterdescription
65	Can add release status	17	add_releasestatus
66	Can change release status	17	change_releasestatus
67	Can delete release status	17	delete_releasestatus
68	Can view release status	17	view_releasestatus
69	Can add stage	18	add_stage
70	Can change stage	18	change_stage
71	Can delete stage	18	delete_stage
72	Can view stage	18	view_stage
73	Can add release	19	add_release
74	Can change release	19	change_release
75	Can delete release	19	delete_release
76	Can view release	19	view_release
77	Can add log source	20	add_logsource
78	Can change log source	20	change_logsource
79	Can delete log source	20	delete_logsource
80	Can view log source	20	view_logsource
81	Can add ECS Fieldset	21	add_ecsfieldset
82	Can change ECS Fieldset	21	change_ecsfieldset
83	Can delete ECS Fieldset	21	delete_ecsfieldset
84	Can view ECS Fieldset	21	view_ecsfieldset
85	Can add ECS Field - Allowed Values	22	add_ecsfieldallowedvalues
86	Can change ECS Field - Allowed Values	22	change_ecsfieldallowedvalues
87	Can delete ECS Field - Allowed Values	22	delete_ecsfieldallowedvalues
88	Can view ECS Field - Allowed Values	22	view_ecsfieldallowedvalues
89	Can add example event	23	add_exampleevent
90	Can change example event	23	change_exampleevent
91	Can delete example event	23	delete_exampleevent
92	Can view example event	23	view_exampleevent
93	Can add ECS Multi-Field	24	add_ecsmultifield
94	Can change ECS Multi-Field	24	change_ecsmultifield
95	Can delete ECS Multi-Field	24	delete_ecsmultifield
96	Can view ECS Multi-Field	24	view_ecsmultifield
97	Can add ECS Fieldset Reused	25	add_ecsfieldsetreused
98	Can change ECS Fieldset Reused	25	change_ecsfieldsetreused
99	Can delete ECS Fieldset Reused	25	delete_ecsfieldsetreused
100	Can view ECS Fieldset Reused	25	view_ecsfieldsetreused
101	Can add grok pattern category	26	add_grokpatterncategory
102	Can change grok pattern category	26	change_grokpatterncategory
103	Can delete grok pattern category	26	delete_grokpatterncategory
104	Can view grok pattern category	26	view_grokpatterncategory
105	Can add grok pattern	27	add_grokpattern
106	Can change grok pattern	27	change_grokpattern
107	Can delete grok pattern	27	delete_grokpattern
108	Can view grok pattern	27	view_grokpattern
\.


--
-- Data for Name: auth_user; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) FROM stdin;
1	pbkdf2_sha256$320000$O0gR9mM2zgGEyV8Bf2e1lP$uGW9IAixXw5d79u7yFrQH+q/Bb/shNu2k1hAqKLcK54=	\N	f	dev			dev@example.de	f	f	2023-11-21 09:57:30.484551+00
2	pbkdf2_sha256$320000$HwWpALN1OA1RQHaFjKzpkw$4QO1ABfJuNVwgtYFBdEWjtfTfb2KDHwCLQUk7f1c2lU=	\N	f	system			system@example.de	f	f	2023-11-21 09:57:31.366661+00
3	!OhqiXIPnQtcW8kXXTLl6tNsPCZLLvehpSWMNoKau	\N	f	logprep				f	t	2023-12-04 08:51:40.939417+00
\.


--
-- Data for Name: auth_user_groups; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_user_groups (id, user_id, group_id) FROM stdin;
\.


--
-- Data for Name: auth_user_user_permissions; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.auth_user_user_permissions (id, user_id, permission_id) FROM stdin;
\.


--
-- Data for Name: django_admin_log; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.django_admin_log (id, action_time, object_id, object_repr, action_flag, change_message, content_type_id, user_id) FROM stdin;
\.


--
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.django_content_type (id, app_label, model) FROM stdin;
1	admin	logentry
2	auth	permission
3	auth	group
4	auth	user
5	contenttypes	contenttype
6	sessions	session
7	fda	ecsfield
8	fda	ecsfieldlevel
9	fda	ecsfieldtype
10	fda	ecsversion
11	fda	logclass
12	fda	logclassmapping
13	fda	logclassstatus
14	fda	logtarget
15	fda	mappingfunction
16	fda	parameterdescription
17	fda	releasestatus
18	fda	stage
19	fda	release
20	fda	logsource
21	fda	ecsfieldset
22	fda	ecsfieldallowedvalues
23	fda	exampleevent
24	fda	ecsmultifield
25	fda	ecsfieldsetreused
26	fda	grokpatterncategory
27	fda	grokpattern
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	contenttypes	0001_initial	2023-11-21 09:57:28.401472+00
2	auth	0001_initial	2023-11-21 09:57:28.669613+00
3	admin	0001_initial	2023-11-21 09:57:28.745273+00
4	admin	0002_logentry_remove_auto_add	2023-11-21 09:57:28.759733+00
5	admin	0003_logentry_add_action_flag_choices	2023-11-21 09:57:28.77236+00
6	contenttypes	0002_remove_content_type_name	2023-11-21 09:57:28.78374+00
7	auth	0002_alter_permission_name_max_length	2023-11-21 09:57:28.791932+00
8	auth	0003_alter_user_email_max_length	2023-11-21 09:57:28.802709+00
9	auth	0004_alter_user_username_opts	2023-11-21 09:57:28.80986+00
10	auth	0005_alter_user_last_login_null	2023-11-21 09:57:28.817109+00
11	auth	0006_require_contenttypes_0002	2023-11-21 09:57:28.82093+00
12	auth	0007_alter_validators_add_error_messages	2023-11-21 09:57:28.831615+00
13	auth	0008_alter_user_username_max_length	2023-11-21 09:57:28.856134+00
14	auth	0009_alter_user_last_name_max_length	2023-11-21 09:57:28.873735+00
15	auth	0010_alter_group_name_max_length	2023-11-21 09:57:28.888282+00
16	auth	0011_update_proxy_permissions	2023-11-21 09:57:28.896948+00
17	auth	0012_alter_user_first_name_max_length	2023-11-21 09:57:28.905583+00
18	fda	0001_initial	2023-11-21 09:57:30.457541+00
19	fda	0002_base_release	2023-11-21 09:57:30.56249+00
20	fda	0003_logclassmapping_output_keys_and_more	2023-11-21 09:57:30.681568+00
21	fda	0004_alter_release_ecs_version	2023-11-21 09:57:30.700894+00
22	fda	0005_alter_logclassmapping_output_keys	2023-11-21 09:57:30.716298+00
23	fda	0006_delete_mappingoutput	2023-11-21 09:57:30.723419+00
24	fda	0007_mappingfunction_parent_function	2023-11-21 09:57:30.75165+00
25	fda	0008_remove_logtarget_created_remove_logtarget_created_by_and_more	2023-11-21 09:57:30.848748+00
26	fda	0009_alter_logtarget_options	2023-11-21 09:57:30.857667+00
27	fda	0010_alter_logclass_unique_together	2023-11-21 09:57:30.893754+00
28	fda	0011_grokpatterncategory_grokpattern	2023-11-21 09:57:30.975966+00
29	fda	0012_alter_stage_options_stage_ordering_and_more	2023-11-21 09:57:31.138768+00
30	fda	0013_remove_stage_id_alter_release_stage	2023-11-21 09:57:31.237268+00
31	fda	0014_alter_stage_name	2023-11-21 09:57:31.348952+00
32	fda	0015_create_system_user	2023-11-21 09:57:31.44198+00
33	sessions	0001_initial	2023-11-21 09:57:31.492188+00
34	fda	0016_add_ids_to_processors	2024-01-18 13:09:30.095437+00
\.


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.django_session (session_key, session_data, expire_date) FROM stdin;
\.


--
-- Data for Name: fda_ecsfield; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfield (id, created, updated, md5_hash, name, flat_name, is_ecs, description, required, short, example, index, format, input_format, output_format, output_precision, pattern, expected_values, "normalize", beta, doc_values, object_type, ignore_above, scaling_factor, custom_comment, custom_help, custom_description, custom_example, created_by_id, ecs_fieldset_id, level_id, type_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsfieldallowedvalues; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfieldallowedvalues (id, created, updated, md5_hash, name, description, expected_event_types, created_by_id, ecs_field_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsfieldlevel; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfieldlevel (id, name, is_ecs) FROM stdin;
\.


--
-- Data for Name: fda_ecsfieldset; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfieldset (id, created, updated, md5_hash, name, is_ecs, root, title, description, comment, short, short_override, beta, footnote, custom_comment, custom_description, created_by_id, ecs_version_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsfieldsetreused; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfieldsetreused (id, created, updated, md5_hash, is_ecs, reused_as, top_level, beta, short_override, created_by_id, ecs_fieldset_id, ecs_reused_at_fieldset_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsfieldtype; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsfieldtype (id, name, is_ecs) FROM stdin;
\.


--
-- Data for Name: fda_ecsmultifield; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsmultifield (id, created, updated, md5_hash, is_ecs, name, created_by_id, ecs_version_id, type_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsmultifield_ecs_fields; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsmultifield_ecs_fields (id, ecsmultifield_id, ecsfield_id) FROM stdin;
\.


--
-- Data for Name: fda_ecsversion; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_ecsversion (id, created, updated, version_major, version_minor, created_by_id, updated_by_id) FROM stdin;
18f6b7af-a59a-4e17-8361-1928341f17a8	2023-11-21 09:57:30.559794+00	\N	0	0	1	\N
4aff3b7b-2060-45ad-af71-20ef9e16f6b8	2023-12-04 08:54:12.439767+00	\N	0	0	3	\N
\.


--
-- Data for Name: fda_exampleevent; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_exampleevent (id, created, updated, is_custom, name, document, created_by_id, log_class_id, log_source_id, updated_by_id) FROM stdin;
33582d54-5273-491e-a79f-807b8b7cabc3	2023-12-04 09:01:33.084696+00	\N	t	Example Event	{\n  "@timestamp": "1699211755000",\n  "message": "2023-11-5-20-13-17+0100 This is an example message for a request. Source: [127.0.0.1:8000], Target: [22:156.21:AS:CD:EG:12:98:ff]. Some more infos: (SystemA-SystemB-SystemC) (Server1 Server2 Server3)",\n  "meta": {\n    "provider": {\n      "name": "provider",\n      "id": "ABF"\n    }\n  }\n}	3	270fd502-ad78-48fb-ae9d-3066b882f0bf	\N	\N
\.


--
-- Data for Name: fda_grokpattern; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_grokpattern (id, type, pattern, category_id) FROM stdin;
CLOUDFRONT_ACCESS_LOG	ecs	(?<timestamp>%{YEAR}-%{MONTHNUM}-%{MONTHDAY}\\t%{TIME})\\t%{CLOUDFRONT_EDGE_LOCATION:[aws][cloudfront][x_edge_location]}\\t(?:-|%{INT:[destination][bytes]:int})\\t%{IPORHOST:[source][ip]}\\t%{WORD:[http][request][method]}\\t%{HOSTNAME:[url][domain]}\\t%{NOTSPACE:[url][path]}\\t(?:(?:000)|%{INT:[http][response][status_code]:int})\\t(?:-|%{DATA:[http][request][referrer]})\\t%{DATA:[user_agent][original]}\\t(?:-|%{DATA:[url][query]})\\t(?:-|%{DATA:[aws][cloudfront][http][request][cookie]})\\t%{WORD:[aws][cloudfront][x_edge_result_type]}\\t%{NOTSPACE:[aws][cloudfront][x_edge_request_id]}\\t%{HOSTNAME:[aws][cloudfront][http][request][host]}\\t%{URIPROTO:[network][protocol]}\\t(?:-|%{INT:[source][bytes]:int})\\t%{NUMBER:[aws][cloudfront][time_taken]:float}\\t(?:-|%{IP:[network][forwarded_ip]})\\t(?:-|%{DATA:[aws][cloudfront][ssl_protocol]})\\t(?:-|%{NOTSPACE:[tls][cipher]})\\t%{WORD:[aws][cloudfront][x_edge_response_result_type]}(?:\\t(?:-|HTTP/%{NUMBER:[http][version]})\\t(?:-|%{DATA:[aws][cloudfront][fle_status]})\\t(?:-|%{DATA:[aws][cloudfront][fle_encrypted_fields]})\\t%{INT:[source][port]:int}\\t%{NUMBER:[aws][cloudfront][time_to_first_byte]:float}\\t(?:-|%{DATA:[aws][cloudfront][x_edge_detailed_result_type]})\\t(?:-|%{NOTSPACE:[http][request][mime_type]})\\t(?:-|%{INT:[aws][cloudfront][http][request][size]:int})\\t(?:-|%{INT:[aws][cloudfront][http][request][range][start]:int})\\t(?:-|%{INT:[aws][cloudfront][http][request][range][end]:int}))?	aws
BACULA_CAPACITY	ecs	%{INT}{1,3}(,%{INT}{3})*	bacula
BACULA_VERSION	ecs	%{USER}	bacula
BACULA_JOB	ecs	%{USER}	bacula
BACULA_LOG_MAX_CAPACITY	ecs	User defined maximum volume capacity %{BACULA_CAPACITY:[bacula][volume][max_capacity]} exceeded on device \\"%{BACULA_DEVICE:[bacula][volume][device]}\\" \\(%{BACULA_DEVICEPATH:[bacula][volume][path]}\\).?	bacula
BACULA_LOG_END_VOLUME	ecs	End of medium on Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" Bytes=%{BACULA_CAPACITY:[bacula][volume][bytes]} Blocks=%{BACULA_CAPACITY:[bacula][volume][blocks]} at %{BACULA_TIMESTAMP:[bacula][timestamp]}.	bacula
BACULA_LOG_NEW_VOLUME	ecs	Created new Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" in catalog.	bacula
BACULA_LOG_NEW_LABEL	ecs	Labeled new Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" on (?:file )?device \\"%{BACULA_DEVICE:[bacula][volume][device]}\\" \\(%{BACULA_DEVICEPATH:[bacula][volume][path]}\\).	bacula
BACULA_LOG_WROTE_LABEL	ecs	Wrote label to prelabeled Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" on device \\"%{BACULA_DEVICE:[bacula][volume][device]}\\" \\(%{BACULA_DEVICEPATH:[bacula][volume][path]}\\)	bacula
BACULA_LOG_NEW_MOUNT	ecs	New volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" mounted on device \\"%{BACULA_DEVICE:[bacula][volume][device]}\\" \\(%{BACULA_DEVICEPATH:[bacula][volume][path]}\\) at %{BACULA_TIMESTAMP:[bacula][timestamp]}.	bacula
BACULA_LOG_NOOPEN	ecs	\\s*Cannot open %{DATA}: ERR=%{GREEDYDATA:[error][message]}	bacula
BACULA_LOG_NOOPENDIR	ecs	\\s*Could not open directory \\"?%{DATA:[file][path]}\\"?: ERR=%{GREEDYDATA:[error][message]}	bacula
BACULA_LOG_NOSTAT	ecs	\\s*Could not stat %{DATA:[file][path]}: ERR=%{GREEDYDATA:[error][message]}	bacula
BACULA_LOG_NOJOBS	ecs	There are no more Jobs associated with Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\". Marking it purged.	bacula
BACULA_LOG_ALL_RECORDS_PRUNED	ecs	.*?All records pruned from Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\"; marking it \\"Purged\\"	bacula
BACULA_LOG_BEGIN_PRUNE_JOBS	ecs	Begin pruning Jobs older than %{INT} month %{INT} days .	bacula
BACULA_LOG_BEGIN_PRUNE_FILES	ecs	Begin pruning Files.	bacula
BACULA_LOG_PRUNED_JOBS	ecs	Pruned %{INT} Jobs* for client %{BACULA_HOST:[bacula][client][name]} from catalog.	bacula
BACULA_LOG_PRUNED_FILES	ecs	Pruned Files from %{INT} Jobs* for client %{BACULA_HOST:[bacula][client][name]} from catalog.	bacula
BACULA_LOG_STARTJOB	ecs	Start Backup JobId %{INT}, Job=%{BACULA_JOB:[bacula][job][name]}	bacula
BACULA_LOG_STARTRESTORE	ecs	Start Restore Job %{BACULA_JOB:[bacula][job][name]}	bacula
BACULA_LOG_USEDEVICE	ecs	Using Device \\"%{BACULA_DEVICE:[bacula][volume][device]}\\"	bacula
BACULA_LOG_DIFF_FS	ecs	\\s*%{UNIXPATH} is a different filesystem. Will not descend from %{UNIXPATH} into it.	bacula
BACULA_LOG_JOBEND	ecs	Job write elapsed time = %{DATA:[bacula][job][elapsed_time]}, Transfer rate = %{NUMBER} (K|M|G)? Bytes/second	bacula
BACULA_LOG_NOPRUNE_JOBS	ecs	No Jobs found to prune.	bacula
BACULA_LOG_NOPRUNE_FILES	ecs	No Files found to prune.	bacula
BACULA_LOG_VOLUME_PREVWRITTEN	ecs	Volume \\"?%{BACULA_VOLUME:[bacula][volume][name]}\\"? previously written, moving to end of data.	bacula
BACULA_LOG_READYAPPEND	ecs	Ready to append to end of Volume \\"%{BACULA_VOLUME:[bacula][volume][name]}\\" size=%{INT:[bacula][volume][size]:int}	bacula
BACULA_LOG_CANCELLING	ecs	Cancelling duplicate JobId=%{INT:[bacula][job][other_id]}.	bacula
BACULA_LOG_MARKCANCEL	ecs	JobId %{INT:[bacula][job][id]}, Job %{BACULA_JOB:[bacula][job][name]} marked to be canceled.	bacula
BACULA_LOG_CLIENT_RBJ	ecs	shell command: run ClientRunBeforeJob \\"%{GREEDYDATA:[bacula][job][client_run_before_command]}\\"	bacula
BACULA_LOG_VSS	ecs	(Generate )?VSS (Writer)?	bacula
BACULA_LOG_MAXSTART	ecs	Fatal [eE]rror: Job canceled because max start delay time exceeded.	bacula
BACULA_LOG_DUPLICATE	ecs	Fatal [eE]rror: JobId %{INT:[bacula][job][other_id]} already running. Duplicate job not allowed.	bacula
BACULA_LOG_NOJOBSTAT	ecs	Fatal [eE]rror: No Job status returned from FD.	bacula
BACULA_LOG_FATAL_CONN	ecs	Fatal [eE]rror: bsock.c:133 Unable to connect to (Client: %{BACULA_HOST:[bacula][client][name]}|Storage daemon) on %{IPORHOST:[client][address]}:%{POSINT:[client][port]:int}. ERR=%{GREEDYDATA:[error][message]}	bacula
BACULA_LOG_NO_CONNECT	ecs	Warning: bsock.c:127 Could not connect to (Client: %{BACULA_HOST:[bacula][client][name]}|Storage daemon) on %{IPORHOST:[client][address]}:%{POSINT:[client][port]:int}. ERR=%{GREEDYDATA:[error][message]}	bacula
BACULA_LOG_NO_AUTH	ecs	Fatal error: Unable to authenticate with File daemon at \\"?%{IPORHOST:[client][address]}(?::%{POSINT:[client][port]:int})?\\"?. Possible causes:	bacula
BACULA_LOG_NOSUIT	ecs	No prior or suitable Full backup found in catalog. Doing FULL backup.	bacula
BACULA_LOG_NOPRIOR	ecs	No prior Full backup Job record found.	bacula
BACULA_LOG_JOB	ecs	(Error: )?Bacula %{BACULA_HOST} %{BACULA_VERSION} \\(%{BACULA_VERSION}\\):	bacula
BACULA_LOG_ENDPRUNE	ecs	End auto prune.	bacula
BACULA_LOG	ecs	%{BACULA_TIMESTAMP:timestamp} %{BACULA_HOST:[host][hostname]}(?: JobId %{INT:[bacula][job][id]})?:? (%{BACULA_LOG_MAX_CAPACITY}|%{BACULA_LOG_END_VOLUME}|%{BACULA_LOG_NEW_VOLUME}|%{BACULA_LOG_NEW_LABEL}|%{BACULA_LOG_WROTE_LABEL}|%{BACULA_LOG_NEW_MOUNT}|%{BACULA_LOG_NOOPEN}|%{BACULA_LOG_NOOPENDIR}|%{BACULA_LOG_NOSTAT}|%{BACULA_LOG_NOJOBS}|%{BACULA_LOG_ALL_RECORDS_PRUNED}|%{BACULA_LOG_BEGIN_PRUNE_JOBS}|%{BACULA_LOG_BEGIN_PRUNE_FILES}|%{BACULA_LOG_PRUNED_JOBS}|%{BACULA_LOG_PRUNED_FILES}|%{BACULA_LOG_ENDPRUNE}|%{BACULA_LOG_STARTJOB}|%{BACULA_LOG_STARTRESTORE}|%{BACULA_LOG_USEDEVICE}|%{BACULA_LOG_DIFF_FS}|%{BACULA_LOG_JOBEND}|%{BACULA_LOG_NOPRUNE_JOBS}|%{BACULA_LOG_NOPRUNE_FILES}|%{BACULA_LOG_VOLUME_PREVWRITTEN}|%{BACULA_LOG_READYAPPEND}|%{BACULA_LOG_CANCELLING}|%{BACULA_LOG_MARKCANCEL}|%{BACULA_LOG_CLIENT_RBJ}|%{BACULA_LOG_VSS}|%{BACULA_LOG_MAXSTART}|%{BACULA_LOG_DUPLICATE}|%{BACULA_LOG_NOJOBSTAT}|%{BACULA_LOG_FATAL_CONN}|%{BACULA_LOG_NO_CONNECT}|%{BACULA_LOG_NO_AUTH}|%{BACULA_LOG_NOSUIT}|%{BACULA_LOG_JOB}|%{BACULA_LOG_NOPRIOR})	bacula
BACULA_LOGLINE	ecs	%{BACULA_LOG}	bacula
BIND9_TIMESTAMP	ecs	%{MONTHDAY}[-]%{MONTH}[-]%{YEAR} %{TIME}	bind
BIND9_DNSTYPE	ecs	(?:A|AAAA|CAA|CDNSKEY|CDS|CERT|CNAME|CSYNC|DLV|DNAME|DNSKEY|DS|HINFO|LOC|MX|NAPTR|NS|NSEC|NSEC3|OPENPGPKEY|PTR|RRSIG|RP|SIG|SMIMEA|SOA|SRV|TSIG|TXT|URI)	bind
BIND9_CATEGORY	ecs	(?:queries)	bind
BIND9_QUERYLOGBASE	ecs	client(:? @0x(?:[0-9A-Fa-f]+))? %{IP:[client][ip]}#%{POSINT:[client][port]:int} \\(%{GREEDYDATA:[bind][log][question][name]}\\): query: %{GREEDYDATA:[dns][question][name]} (?<[dns][question][class]>IN) %{BIND9_DNSTYPE:[dns][question][type]}(:? %{DATA:[bind][log][question][flags]})? \\(%{IP:[server][ip]}\\)	bind
BIND9_QUERYLOG	ecs	%{BIND9_TIMESTAMP:timestamp} %{BIND9_CATEGORY:[bind][log][category]}: %{LOGLEVEL:[log][level]}: %{BIND9_QUERYLOGBASE}	bind
BRO_HTTP	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{INT:[zeek][http][trans_depth]:int}\\t(?:-|%{WORD:[http][request][method]})\\t(?:-|%{BRO_DATA:[url][domain]})\\t(?:-|%{BRO_DATA:[url][original]})\\t(?:-|%{BRO_DATA:[http][request][referrer]})\\t(?:-|%{BRO_DATA:[user_agent][original]})\\t(?:-|%{NUMBER:[http][request][body][bytes]:int})\\t(?:-|%{NUMBER:[http][response][body][bytes]:int})\\t(?:-|%{POSINT:[http][response][status_code]:int})\\t(?:-|%{DATA:[zeek][http][status_msg]})\\t(?:-|%{POSINT:[zeek][http][info_code]:int})\\t(?:-|%{DATA:[zeek][http][info_msg]})\\t(?:-|%{BRO_DATA:[zeek][http][filename]})\\t(?:\\(empty\\)|%{BRO_DATA:[zeek][http][tags]})\\t(?:-|%{BRO_DATA:[url][username]})\\t(?:-|%{BRO_DATA:[url][password]})\\t(?:-|%{BRO_DATA:[zeek][http][proxied]})\\t(?:-|%{BRO_DATA:[zeek][http][orig_fuids]})\\t(?:-|%{BRO_DATA:[http][request][mime_type]})\\t(?:-|%{BRO_DATA:[zeek][http][resp_fuids]})\\t(?:-|%{BRO_DATA:[http][response][mime_type]})	bro
BRO_DNS	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{WORD:[network][transport]}\\t(?:-|%{INT:[dns][id]:int})\\t(?:-|%{BRO_DATA:[dns][question][name]})\\t(?:-|%{INT:[zeek][dns][qclass]:int})\\t(?:-|%{BRO_DATA:[zeek][dns][qclass_name]})\\t(?:-|%{INT:[zeek][dns][qtype]:int})\\t(?:-|%{BRO_DATA:[dns][question][type]})\\t(?:-|%{INT:[zeek][dns][rcode]:int})\\t(?:-|%{BRO_DATA:[dns][response_code]})\\t(?:-|%{BRO_BOOL:[zeek][dns][AA]})\\t(?:-|%{BRO_BOOL:[zeek][dns][TC]})\\t(?:-|%{BRO_BOOL:[zeek][dns][RD]})\\t(?:-|%{BRO_BOOL:[zeek][dns][RA]})\\t(?:-|%{NONNEGINT:[zeek][dns][Z]:int})\\t(?:-|%{BRO_DATA:[zeek][dns][answers]})\\t(?:-|%{DATA:[zeek][dns][TTLs]})\\t(?:-|%{BRO_BOOL:[zeek][dns][rejected]})	bro
BRO_CONN	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{WORD:[network][transport]}\\t(?:-|%{BRO_DATA:[network][protocol]})\\t(?:-|%{NUMBER:[zeek][connection][duration]:float})\\t(?:-|%{INT:[zeek][connection][orig_bytes]:int})\\t(?:-|%{INT:[zeek][connection][resp_bytes]:int})\\t(?:-|%{BRO_DATA:[zeek][connection][state]})\\t(?:-|%{BRO_BOOL:[zeek][connection][local_orig]})\\t(?:(?:-|%{BRO_BOOL:[zeek][connection][local_resp]})\\t)?(?:-|%{INT:[zeek][connection][missed_bytes]:int})\\t(?:-|%{BRO_DATA:[zeek][connection][history]})\\t(?:-|%{INT:[source][packets]:int})\\t(?:-|%{INT:[source][bytes]:int})\\t(?:-|%{INT:[destination][packets]:int})\\t(?:-|%{INT:[destination][bytes]:int})\\t(?:\\(empty\\)|%{BRO_DATA:[zeek][connection][tunnel_parents]})	bro
BRO_FILES	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][files][fuid]}\\t(?:-|%{IP:[server][ip]})\\t(?:-|%{IP:[client][ip]})\\t(?:-|%{BRO_DATA:[zeek][files][session_ids]})\\t(?:-|%{BRO_DATA:[zeek][files][source]})\\t(?:-|%{INT:[zeek][files][depth]:int})\\t(?:-|%{BRO_DATA:[zeek][files][analyzers]})\\t(?:-|%{BRO_DATA:[file][mime_type]})\\t(?:-|%{BRO_DATA:[file][name]})\\t(?:-|%{NUMBER:[zeek][files][duration]:float})\\t(?:-|%{BRO_DATA:[zeek][files][local_orig]})\\t(?:-|%{BRO_BOOL:[zeek][files][is_orig]})\\t(?:-|%{INT:[zeek][files][seen_bytes]:int})\\t(?:-|%{INT:[file][size]:int})\\t(?:-|%{INT:[zeek][files][missing_bytes]:int})\\t(?:-|%{INT:[zeek][files][overflow_bytes]:int})\\t(?:-|%{BRO_BOOL:[zeek][files][timedout]})\\t(?:-|%{BRO_DATA:[zeek][files][parent_fuid]})\\t(?:-|%{BRO_DATA:[file][hash][md5]})\\t(?:-|%{BRO_DATA:[file][hash][sha1]})\\t(?:-|%{BRO_DATA:[file][hash][sha256]})\\t(?:-|%{BRO_DATA:[zeek][files][extracted]})	bro
EXIM_MSGID	ecs	[0-9A-Za-z]{6}-[0-9A-Za-z]{6}-[0-9A-Za-z]{2}	exim
EXIM_FLAGS	ecs	(?:<=|=>|->|\\*>|\\*\\*|==|<>|>>)	exim
EXIM_DATE	ecs	(:?%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{TIME})	exim
EXIM_PID	ecs	\\[%{POSINT:[process][pid]:int}\\]	exim
EXIM_QT	ecs	((\\d+y)?(\\d+w)?(\\d+d)?(\\d+h)?(\\d+m)?(\\d+s)?)	exim
EXIM_EXCLUDE_TERMS	ecs	(Message is frozen|(Start|End) queue run| Warning: | retry time not reached | no (IP address|host name) found for (IP address|host) | unexpected disconnection while reading SMTP command | no immediate delivery: |another process is handling this message)	exim
EXIM_REMOTE_HOST	ecs	(H=(%{NOTSPACE:[source][address]} )?(\\(%{NOTSPACE:[exim][log][remote_address]}\\) )?\\[%{IP:[source][ip]}\\](?::%{POSINT:[source][port]:int})?)	exim
EXIM_INTERFACE	ecs	(I=\\[%{IP:[destination][ip]}\\](?::%{NUMBER:[destination][port]:int}))	exim
EXIM_PROTOCOL	ecs	(P=%{NOTSPACE:[network][protocol]})	exim
EXIM_MSG_SIZE	ecs	(S=%{NUMBER:[exim][log][message][size]:int})	exim
EXIM_HEADER_ID	ecs	(id=%{NOTSPACE:[exim][log][header_id]})	exim
EXIM_QUOTED_CONTENT	ecs	(?:\\\\.|[^\\\\"])*	exim
EXIM_SUBJECT	ecs	(T="%{EXIM_QUOTED_CONTENT:[exim][log][message][subject]}")	exim
EXIM_UNKNOWN_FIELD	ecs	(?:[A-Za-z0-9]{1,4}=(?:%{QUOTEDSTRING}|%{NOTSPACE}))	exim
EXIM_NAMED_FIELDS	ecs	(?: (?:%{EXIM_REMOTE_HOST}|%{EXIM_INTERFACE}|%{EXIM_PROTOCOL}|%{EXIM_MSG_SIZE}|%{EXIM_HEADER_ID}|%{EXIM_SUBJECT}|%{EXIM_UNKNOWN_FIELD}))*	exim
EXIM_MESSAGE_ARRIVAL	ecs	%{EXIM_DATE:timestamp} (?:%{EXIM_PID} )?%{EXIM_MSGID:[exim][log][message][id]} (?<[exim][log][flags]><=) (?<[exim][log][status]>[a-z:] )?%{EMAILADDRESS:[exim][log][sender][email]}%{EXIM_NAMED_FIELDS}(?:(?: from <?%{DATA:[exim][log][sender][original]}>?)? for %{EMAILADDRESS:[exim][log][recipient][email]})?	exim
EXIM	ecs	%{EXIM_MESSAGE_ARRIVAL}	exim
NETSCREENSESSIONLOG	ecs	%{SYSLOGTIMESTAMP:timestamp} %{IPORHOST:[observer][hostname]} %{NOTSPACE:[observer][name]}: (?<[observer][product]>NetScreen) device_id=%{WORD:[netscreen][device_id]} .*?(system-\\w+-%{NONNEGINT:[event][code]}\\(%{WORD:[netscreen][session][type]}\\))?: start_time="%{DATA:[netscreen][session][start_time]}" duration=%{INT:[netscreen][session][duration]:int} policy_id=%{INT:[netscreen][policy_id]} service=%{DATA:[netscreen][service]} proto=%{INT:[netscreen][protocol_number]:int} src zone=%{WORD:[observer][ingress][zone]} dst zone=%{WORD:[observer][egress][zone]} action=%{WORD:[event][action]} sent=%{INT:[source][bytes]:int} rcvd=%{INT:[destination][bytes]:int} src=%{IPORHOST:[source][address]} dst=%{IPORHOST:[destination][address]}(?: src_port=%{INT:[source][port]:int} dst_port=%{INT:[destination][port]:int})?(?: src-xlated ip=%{IP:[source][nat][ip]} port=%{INT:[source][nat][port]:int} dst-xlated ip=%{IP:[destination][nat][ip]} port=%{INT:[destination][nat][port]:int})?(?: session_id=%{INT:[netscreen][session][id]} reason=%{GREEDYDATA:[netscreen][session][reason]})?	firewalls
CISCO_TAGGED_SYSLOG	ecs	^<%{POSINT:[log][syslog][priority]:int}>%{CISCOTIMESTAMP:timestamp}( %{SYSLOGHOST:[host][hostname]})? ?: %%{CISCOTAG:[cisco][asa][tag]}:	firewalls
CISCOTIMESTAMP	ecs	%{MONTH} +%{MONTHDAY}(?: %{YEAR})? %{TIME}	firewalls
CISCOTAG	ecs	[A-Z0-9]+-%{INT}-(?:[A-Z0-9_]+)	firewalls
CISCO_ACTION	ecs	Built|Teardown|Deny|Denied|denied|requested|permitted|denied by ACL|discarded|est-allowed|Dropping|created|deleted	firewalls
CISCO_REASON	ecs	Duplicate TCP SYN|Failed to locate egress interface|Invalid transport field|No matching connection|DNS Response|DNS Query|(?:%{WORD}\\s*)*	firewalls
CISCO_DIRECTION	ecs	Inbound|inbound|Outbound|outbound	firewalls
CISCO_XLATE_TYPE	ecs	static|dynamic	firewalls
CISCO_HITCOUNT_INTERVAL	ecs	hit-cnt %{INT:[cisco][asa][hit_count]:int} (?:first hit|%{INT:[cisco][asa][interval]:int}-second interval)	firewalls
CISCO_SRC_IP_USER	ecs	%{NOTSPACE:[observer][ingress][interface][name]}:%{IP:[source][ip]}(?:\\(%{DATA:[source][user][name]}\\))?	firewalls
CISCO_DST_IP_USER	ecs	%{NOTSPACE:[observer][egress][interface][name]}:%{IP:[destination][ip]}(?:\\(%{DATA:[destination][user][name]}\\))?	firewalls
CISCO_SRC_HOST_PORT_USER	ecs	%{NOTSPACE:[observer][ingress][interface][name]}:(?:(?:%{IP:[source][ip]})|(?:%{HOSTNAME:[source][address]}))(?:/%{INT:[source][port]:int})?(?:\\(%{DATA:[source][user][name]}\\))?	firewalls
CISCO_DST_HOST_PORT_USER	ecs	%{NOTSPACE:[observer][egress][interface][name]}:(?:(?:%{IP:[destination][ip]})|(?:%{HOSTNAME:[destination][address]}))(?:/%{INT:[destination][port]:int})?(?:\\(%{DATA:[destination][user][name]}\\))?	firewalls
CISCOFW104001	ecs	\\((?:Primary|Secondary)\\) Switching to ACTIVE - %{GREEDYDATA:[event][reason]}	firewalls
CISCOFW104002	ecs	\\((?:Primary|Secondary)\\) Switching to STANDBY - %{GREEDYDATA:[event][reason]}	firewalls
CISCOFW104003	ecs	\\((?:Primary|Secondary)\\) Switching to FAILED\\.	firewalls
CISCOFW104004	ecs	\\((?:Primary|Secondary)\\) Switching to OK\\.	firewalls
CISCOFW105003	ecs	\\((?:Primary|Secondary)\\) Monitoring on [Ii]nterface %{NOTSPACE:[network][interface][name]} waiting	firewalls
CISCOFW105004	ecs	\\((?:Primary|Secondary)\\) Monitoring on [Ii]nterface %{NOTSPACE:[network][interface][name]} normal	firewalls
CISCOFW105005	ecs	\\((?:Primary|Secondary)\\) Lost Failover communications with mate on [Ii]nterface %{NOTSPACE:[network][interface][name]}	firewalls
CISCOFW105008	ecs	\\((?:Primary|Secondary)\\) Testing [Ii]nterface %{NOTSPACE:[network][interface][name]}	firewalls
CISCOFW105009	ecs	\\((?:Primary|Secondary)\\) Testing on [Ii]nterface %{NOTSPACE:[network][interface][name]} (?:Passed|Failed)	firewalls
CISCOFW106001	ecs	%{CISCO_DIRECTION:[cisco][asa][network][direction]} %{WORD:[cisco][asa][network][transport]} connection %{CISCO_ACTION:[cisco][asa][outcome]} from %{IP:[source][ip]}/%{INT:[source][port]:int} to %{IP:[destination][ip]}/%{INT:[destination][port]:int} flags %{DATA:[cisco][asa][tcp_flags]} on interface %{NOTSPACE:[observer][egress][interface][name]}	firewalls
CISCOFW106006_106007_106010	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{CISCO_DIRECTION:[cisco][asa][network][direction]} %{WORD:[cisco][asa][network][transport]} (?:from|src) %{IP:[source][ip]}/%{INT:[source][port]:int}(?:\\(%{DATA:[source][user][name]}\\))? (?:to|dst) %{IP:[destination][ip]}/%{INT:[destination][port]:int}(?:\\(%{DATA:[destination][user][name]}\\))? (?:(?:on interface %{NOTSPACE:[observer][egress][interface][name]})|(?:due to %{CISCO_REASON:[event][reason]}))	firewalls
CISCOFW106014	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{CISCO_DIRECTION:[cisco][asa][network][direction]} %{WORD:[cisco][asa][network][transport]} src %{CISCO_SRC_IP_USER} dst %{CISCO_DST_IP_USER}\\s?\\(type %{INT:[cisco][asa][icmp_type]:int}, code %{INT:[cisco][asa][icmp_code]:int}\\)	firewalls
CISCOFW106015	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} \\(%{DATA:[cisco][asa][rule_name]}\\) from %{IP:[source][ip]}/%{INT:[source][port]:int} to %{IP:[destination][ip]}/%{INT:[destination][port]:int} flags %{DATA:[cisco][asa][tcp_flags]} on interface %{NOTSPACE:[observer][egress][interface][name]}	firewalls
CISCOFW106021	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} reverse path check from %{IP:[source][ip]} to %{IP:[destination][ip]} on interface %{NOTSPACE:[observer][egress][interface][name]}	firewalls
CISCOFW106023	ecs	%{CISCO_ACTION:[cisco][asa][outcome]}(?: protocol)? %{WORD:[cisco][asa][network][transport]} src %{CISCO_SRC_HOST_PORT_USER} dst %{CISCO_DST_HOST_PORT_USER}( \\(type %{INT:[cisco][asa][icmp_type]:int}, code %{INT:[cisco][asa][icmp_code]:int}\\))? by access-group "?%{DATA:[cisco][asa][rule_name]}"? \\[%{DATA:[@metadata][cisco][asa][hashcode1]}, %{DATA:[@metadata][cisco][asa][hashcode2]}\\]	firewalls
CISCOFW106100_2_3	ecs	access-list %{NOTSPACE:[cisco][asa][rule_name]} %{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} for user '%{DATA:[user][name]}' %{DATA:[observer][ingress][interface][name]}/%{IP:[source][ip]}\\(%{INT:[source][port]:int}\\) -> %{DATA:[observer][egress][interface][name]}/%{IP:[destination][ip]}\\(%{INT:[destination][port]:int}\\) %{CISCO_HITCOUNT_INTERVAL} \\[%{DATA:[@metadata][cisco][asa][hashcode1]}, %{DATA:[@metadata][cisco][asa][hashcode2]}\\]	firewalls
CISCOFW106100	ecs	access-list %{NOTSPACE:[cisco][asa][rule_name]} %{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} %{DATA:[observer][ingress][interface][name]}/%{IP:[source][ip]}\\(%{INT:[source][port]:int}\\)(?:\\(%{DATA:[source][user][name]}\\))? -> %{DATA:[observer][egress][interface][name]}/%{IP:[destination][ip]}\\(%{INT:[destination][port]:int}\\)(?:\\(%{DATA:[source][user][name]}\\))? hit-cnt %{INT:[cisco][asa][hit_count]:int} %{CISCO_INTERVAL} \\[%{DATA:[@metadata][cisco][asa][hashcode1]}, %{DATA:[@metadata][cisco][asa][hashcode2]}\\]	firewalls
CISCOFW304001	ecs	%{IP:[source][ip]}(?:\\(%{DATA:[source][user][name]}\\))? Accessed URL %{IP:[destination][ip]}:%{GREEDYDATA:[url][original]}	firewalls
CISCOFW110002	ecs	%{CISCO_REASON:[event][reason]} for %{WORD:[cisco][asa][network][transport]} from %{DATA:[observer][ingress][interface][name]}:%{IP:[source][ip]}/%{INT:[source][port]:int} to %{IP:[destination][ip]}/%{INT:[destination][port]:int}	firewalls
CISCOFW302010	ecs	%{INT:[cisco][asa][connections][in_use]:int} in use, %{INT:[cisco][asa][connections][most_used]:int} most used	firewalls
CISCOFW302013_302014_302015_302016	ecs	%{CISCO_ACTION:[cisco][asa][outcome]}(?: %{CISCO_DIRECTION:[cisco][asa][network][direction]})? %{WORD:[cisco][asa][network][transport]} connection %{INT:[cisco][asa][connection_id]} for %{NOTSPACE:[observer][ingress][interface][name]}:%{IP:[source][ip]}/%{INT:[source][port]:int}(?: \\(%{IP:[source][nat][ip]}/%{INT:[source][nat][port]:int}\\))?(?:\\(%{DATA:[source][user][name]}\\))? to %{NOTSPACE:[observer][egress][interface][name]}:%{IP:[destination][ip]}/%{INT:[destination][port]:int}( \\(%{IP:[destination][nat][ip]}/%{INT:[destination][nat][port]:int}\\))?(?:\\(%{DATA:[destination][user][name]}\\))?( duration %{TIME:[cisco][asa][duration]} bytes %{INT:[network][bytes]:int})?(?: %{CISCO_REASON:[event][reason]})?(?: \\(%{DATA:[user][name]}\\))?	firewalls
CISCOFW302020_302021	ecs	%{CISCO_ACTION:[cisco][asa][outcome]}(?: %{CISCO_DIRECTION:[cisco][asa][network][direction]})? %{WORD:[cisco][asa][network][transport]} connection for faddr %{IP:[destination][ip]}/%{INT:[cisco][asa][icmp_seq]:int}(?:\\(%{DATA:[destination][user][name]}\\))? gaddr %{IP:[source][nat][ip]}/%{INT:[cisco][asa][icmp_type]:int} laddr %{IP:[source][ip]}/%{INT}(?: \\(%{DATA:[source][user][name]}\\))?	firewalls
CISCOFW305011	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{CISCO_XLATE_TYPE} %{WORD:[cisco][asa][network][transport]} translation from %{DATA:[observer][ingress][interface][name]}:%{IP:[source][ip]}(/%{INT:[source][port]:int})?(?:\\(%{DATA:[source][user][name]}\\))? to %{DATA:[observer][egress][interface][name]}:%{IP:[destination][ip]}/%{INT:[destination][port]:int}	firewalls
CISCOFW313001_313004_313008	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} type=%{INT:[cisco][asa][icmp_type]:int}, code=%{INT:[cisco][asa][icmp_code]:int} from %{IP:[source][ip]} on interface %{NOTSPACE:[observer][egress][interface][name]}(?: to %{IP:[destination][ip]})?	firewalls
CISCOFW313005	ecs	%{CISCO_REASON:[event][reason]} for %{WORD:[cisco][asa][network][transport]} error message: %{WORD} src %{CISCO_SRC_IP_USER} dst %{CISCO_DST_IP_USER} \\(type %{INT:[cisco][asa][icmp_type]:int}, code %{INT:[cisco][asa][icmp_code]:int}\\) on %{NOTSPACE} interface\\.\\s+Original IP payload: %{WORD:[cisco][asa][original_ip_payload][network][transport]} src %{IP:[cisco][asa][original_ip_payload][source][ip]}/%{INT:[cisco][asa][original_ip_payload][source][port]:int}(?:\\(%{DATA:[cisco][asa][original_ip_payload][source][user][name]}\\))? dst %{IP:[cisco][asa][original_ip_payload][destination][ip]}/%{INT:[cisco][asa][original_ip_payload][destination][port]:int}(?:\\(%{DATA:[cisco][asa][original_ip_payload][destination][user][name]}\\))?	firewalls
CISCOFW321001	ecs	Resource '%{DATA:[cisco][asa][resource][name]}' limit of %{POSINT:[cisco][asa][resource][limit]:int} reached for system	firewalls
CISCOFW402117	ecs	%{WORD:[cisco][asa][network][type]}: Received a non-IPSec packet \\(protocol=\\s?%{WORD:[cisco][asa][network][transport]}\\) from %{IP:[source][ip]} to %{IP:[destination][ip]}\\.?	firewalls
CISCOFW402119	ecs	%{WORD:[cisco][asa][network][type]}: Received an %{WORD:[cisco][asa][ipsec][protocol]} packet \\(SPI=\\s?%{DATA:[cisco][asa][ipsec][spi]}, sequence number=\\s?%{DATA:[cisco][asa][ipsec][seq_num]}\\) from %{IP:[source][ip]} \\(user=\\s?%{DATA:[source][user][name]}\\) to %{IP:[destination][ip]} that failed anti-replay checking\\.?	firewalls
CISCOFW419001	ecs	%{CISCO_ACTION:[cisco][asa][outcome]} %{WORD:[cisco][asa][network][transport]} packet from %{NOTSPACE:[observer][ingress][interface][name]}:%{IP:[source][ip]}/%{INT:[source][port]:int} to %{NOTSPACE:[observer][egress][interface][name]}:%{IP:[destination][ip]}/%{INT:[destination][port]:int}, reason: %{GREEDYDATA:[event][reason]}	firewalls
CISCOFW419002	ecs	%{CISCO_REASON:[event][reason]} from %{DATA:[observer][ingress][interface][name]}:%{IP:[source][ip]}/%{INT:[source][port]:int} to %{DATA:[observer][egress][interface][name]}:%{IP:[destination][ip]}/%{INT:[destination][port]:int} with different initial sequence number	firewalls
CISCOFW500004	ecs	%{CISCO_REASON:[event][reason]} for protocol=%{WORD:[cisco][asa][network][transport]}, from %{IP:[source][ip]}/%{INT:[source][port]:int} to %{IP:[destination][ip]}/%{INT:[destination][port]:int}	firewalls
CISCOFW602303_602304	ecs	%{WORD:[cisco][asa][network][type]}: An %{CISCO_DIRECTION:[cisco][asa][network][direction]} %{DATA:[cisco][asa][ipsec][tunnel_type]} SA \\(SPI=\\s?%{DATA:[cisco][asa][ipsec][spi]}\\) between %{IP:[source][ip]} and %{IP:[destination][ip]} \\(user=\\s?%{DATA:[source][user][name]}\\) has been %{CISCO_ACTION:[cisco][asa][outcome]}	firewalls
CISCOFW710001_710002_710003_710005_710006	ecs	%{WORD:[cisco][asa][network][transport]} (?:request|access) %{CISCO_ACTION:[cisco][asa][outcome]} from %{IP:[source][ip]}/%{INT:[source][port]:int} to %{DATA:[observer][egress][interface][name]}:%{IP:[destination][ip]}/%{INT:[destination][port]:int}	firewalls
CISCOFW713172	ecs	Group = %{DATA:[cisco][asa][source][group]}, IP = %{IP:[source][ip]}, Automatic NAT Detection Status:\\s+Remote end\\s*%{DATA:[@metadata][cisco][asa][remote_nat]}\\s*behind a NAT device\\s+This\\s+end\\s*%{DATA:[@metadata][cisco][asa][local_nat]}\\s*behind a NAT device	firewalls
CISCOFW733100	ecs	\\[\\s*%{DATA:[cisco][asa][burst][object]}\\s*\\] drop %{DATA:[cisco][asa][burst][id]} exceeded. Current burst rate is %{INT:[cisco][asa][burst][current_rate]:int} per second, max configured rate is %{INT:[cisco][asa][burst][configured_rate]:int}; Current average rate is %{INT:[cisco][asa][burst][avg_rate]:int} per second, max configured rate is %{INT:[cisco][asa][burst][configured_avg_rate]:int}; Cumulative total count is %{INT:[cisco][asa][burst][cumulative_count]:int}	firewalls
IPTABLES_TCP_FLAGS	ecs	(CWR |ECE |URG |ACK |PSH |RST |SYN |FIN )*	firewalls
IPTABLES_TCP_PART	ecs	(?:SEQ=%{INT:[iptables][tcp][seq]:int}\\s+)?(?:ACK=%{INT:[iptables][tcp][ack]:int}\\s+)?WINDOW=%{INT:[iptables][tcp][window]:int}\\s+RES=0x%{BASE16NUM:[iptables][tcp_reserved_bits]}\\s+%{IPTABLES_TCP_FLAGS:[iptables][tcp][flags]}	firewalls
IPTABLES4_FRAG	ecs	(?:(?<= )(?:CE|DF|MF))*	firewalls
IPTABLES4_PART	ecs	SRC=%{IPV4:[source][ip]}\\s+DST=%{IPV4:[destination][ip]}\\s+LEN=(?:%{INT:[iptables][length]:int})?\\s+TOS=(?:0|0x%{BASE16NUM:[iptables][tos]})?\\s+PREC=(?:0x%{BASE16NUM:[iptables][precedence_bits]})?\\s+TTL=(?:%{INT:[iptables][ttl]:int})?\\s+ID=(?:%{INT:[iptables][id]})?\\s+(?:%{IPTABLES4_FRAG:[iptables][fragment_flags]})?(?:\\s+FRAG: %{INT:[iptables][fragment_offset]:int})?	firewalls
IPTABLES6_PART	ecs	SRC=%{IPV6:[source][ip]}\\s+DST=%{IPV6:[destination][ip]}\\s+LEN=(?:%{INT:[iptables][length]:int})?\\s+TC=(?:0|0x%{BASE16NUM:[iptables][tos]})?\\s+HOPLIMIT=(?:%{INT:[iptables][ttl]:int})?\\s+FLOWLBL=(?:%{INT:[iptables][flow_label]})?	firewalls
IPTABLES	ecs	IN=(?:%{NOTSPACE:[observer][ingress][interface][name]})?\\s+OUT=(?:%{NOTSPACE:[observer][egress][interface][name]})?\\s+(?:MAC=(?:%{COMMONMAC:[destination][mac]})?(?::%{COMMONMAC:[source][mac]})?(?::[A-Fa-f0-9]{2}:[A-Fa-f0-9]{2})?\\s+)?(:?%{IPTABLES4_PART}|%{IPTABLES6_PART}).*?PROTO=(?:%{WORD:[network][transport]})?\\s+SPT=(?:%{INT:[source][port]:int})?\\s+DPT=(?:%{INT:[destination][port]:int})?\\s+(?:%{IPTABLES_TCP_PART})?	firewalls
SHOREWALL	ecs	(?:%{SYSLOGTIMESTAMP:timestamp}) (?:%{WORD:[observer][hostname]}) .*Shorewall:(?:%{WORD:[shorewall][firewall][type]})?:(?:%{WORD:[shorewall][firewall][action]})?.*%{IPTABLES}	firewalls
SFW2_LOG_PREFIX	ecs	SFW2\\-INext\\-%{NOTSPACE:[suse][firewall][action]}	firewalls
SFW2	ecs	((?:%{SYSLOGTIMESTAMP:timestamp})|(?:%{TIMESTAMP_ISO8601:timestamp}))\\s*%{HOSTNAME:[observer][hostname]}.*?%{SFW2_LOG_PREFIX:[suse][firewall][log_prefix]}\\s*%{IPTABLES}	firewalls
USERNAME	ecs	[a-zA-Z0-9._-]+	grok-patterns
USER	ecs	%{USERNAME}	grok-patterns
EMAILLOCALPART	ecs	[a-zA-Z0-9!#$%&'*+\\-/=?^_`{|}~]{1,64}(?:\\.[a-zA-Z0-9!#$%&'*+\\-/=?^_`{|}~]{1,62}){0,63}	grok-patterns
EMAILADDRESS	ecs	%{EMAILLOCALPART}@%{HOSTNAME}	grok-patterns
INT	ecs	(?:[+-]?(?:[0-9]+))	grok-patterns
BASE10NUM	ecs	(?<![0-9.+-])(?>[+-]?(?:(?:[0-9]+(?:\\.[0-9]+)?)|(?:\\.[0-9]+)))	grok-patterns
NUMBER	ecs	(?:%{BASE10NUM})	grok-patterns
BASE16NUM	ecs	(?<![0-9A-Fa-f])(?:[+-]?(?:0x)?(?:[0-9A-Fa-f]+))	grok-patterns
BASE16FLOAT	ecs	\\b(?<![0-9A-Fa-f.])(?:[+-]?(?:0x)?(?:(?:[0-9A-Fa-f]+(?:\\.[0-9A-Fa-f]*)?)|(?:\\.[0-9A-Fa-f]+)))\\b	grok-patterns
POSINT	ecs	\\b(?:[1-9][0-9]*)\\b	grok-patterns
NONNEGINT	ecs	\\b(?:[0-9]+)\\b	grok-patterns
WORD	ecs	\\b\\w+\\b	grok-patterns
NOTSPACE	ecs	\\S+	grok-patterns
GREEDYDATA	ecs	.*	grok-patterns
QUOTEDSTRING	ecs	(?>(?<!\\\\)(?>"(?>\\\\.|[^\\\\"]+)+"|""|(?>'(?>\\\\.|[^\\\\']+)+')|''|(?>`(?>\\\\.|[^\\\\`]+)+`)|``))	grok-patterns
UUID	ecs	[A-Fa-f0-9]{8}-(?:[A-Fa-f0-9]{4}-){3}[A-Fa-f0-9]{12}	grok-patterns
URN	ecs	urn:[0-9A-Za-z][0-9A-Za-z-]{0,31}:(?:%[0-9a-fA-F]{2}|[0-9A-Za-z()+,.:=@;$_!*'/?#-])+	grok-patterns
MAC	ecs	(?:%{CISCOMAC}|%{WINDOWSMAC}|%{COMMONMAC})	grok-patterns
CISCOMAC	ecs	(?:(?:[A-Fa-f0-9]{4}\\.){2}[A-Fa-f0-9]{4})	grok-patterns
WINDOWSMAC	ecs	(?:(?:[A-Fa-f0-9]{2}-){5}[A-Fa-f0-9]{2})	grok-patterns
COMMONMAC	ecs	(?:(?:[A-Fa-f0-9]{2}:){5}[A-Fa-f0-9]{2})	grok-patterns
IPV6	ecs	((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)(\\.(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d)){3}))|:)))(%.+)?	grok-patterns
IPV4	ecs	(?<![0-9])(?:(?:[0-1]?[0-9]{1,2}|2[0-4][0-9]|25[0-5])[.](?:[0-1]?[0-9]{1,2}|2[0-4][0-9]|25[0-5])[.](?:[0-1]?[0-9]{1,2}|2[0-4][0-9]|25[0-5])[.](?:[0-1]?[0-9]{1,2}|2[0-4][0-9]|25[0-5]))(?![0-9])	grok-patterns
IP	ecs	(?:%{IPV6}|%{IPV4})	grok-patterns
HOSTNAME	ecs	\\b(?:[0-9A-Za-z][0-9A-Za-z-]{0,62})(?:\\.(?:[0-9A-Za-z][0-9A-Za-z-]{0,62}))*(\\.?|\\b)	grok-patterns
IPORHOST	ecs	(?:%{IP}|%{HOSTNAME})	grok-patterns
HOSTPORT	ecs	%{IPORHOST}:%{POSINT}	grok-patterns
PATH	ecs	(?:%{UNIXPATH}|%{WINPATH})	grok-patterns
UNIXPATH	ecs	(/[[[:alnum:]]_%!$@:.,+~-]*)+	grok-patterns
TTY	ecs	(?:/dev/(pts|tty([pq])?)(\\w+)?/?(?:[0-9]+))	grok-patterns
WINPATH	ecs	(?>[A-Za-z]+:|\\\\)(?:\\\\[^\\\\?*]*)+	grok-patterns
URIPROTO	ecs	[A-Za-z]([A-Za-z0-9+\\-.]+)+	grok-patterns
URIHOST	ecs	%{IPORHOST}(?::%{POSINT})?	grok-patterns
URIPATH	ecs	(?:/[A-Za-z0-9$.+!*'(){},~:;=@#%&_\\-]*)+	grok-patterns
URIQUERY	ecs	[A-Za-z0-9$.+!*'|(){},~@#%&/=:;_?\\-\\[\\]<>]*	grok-patterns
URIPARAM	ecs	\\?%{URIQUERY}	grok-patterns
URIPATHPARAM	ecs	%{URIPATH}(?:\\?%{URIQUERY})?	grok-patterns
URI	ecs	%{URIPROTO}://(?:%{USER}(?::[^@]*)?@)?(?:%{URIHOST})?(?:%{URIPATH}(?:\\?%{URIQUERY})?)?	grok-patterns
MONTH	ecs	\\b(?:[Jj]an(?:uary|uar)?|[Ff]eb(?:ruary|ruar)?|[Mm](?:a|Ã¤)?r(?:ch|z)?|[Aa]pr(?:il)?|[Mm]a(?:y|i)?|[Jj]un(?:e|i)?|[Jj]ul(?:y|i)?|[Aa]ug(?:ust)?|[Ss]ep(?:tember)?|[Oo](?:c|k)?t(?:ober)?|[Nn]ov(?:ember)?|[Dd]e(?:c|z)(?:ember)?)\\b	grok-patterns
MONTHNUM	ecs	(?:0?[1-9]|1[0-2])	grok-patterns
MONTHNUM2	ecs	(?:0[1-9]|1[0-2])	grok-patterns
MONTHDAY	ecs	(?:(?:0[1-9])|(?:[12][0-9])|(?:3[01])|[1-9])	grok-patterns
DAY	ecs	(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)	grok-patterns
YEAR	ecs	(?>\\d\\d){1,2}	grok-patterns
HOUR	ecs	(?:2[0123]|[01]?[0-9])	grok-patterns
MINUTE	ecs	(?:[0-5][0-9])	grok-patterns
SECOND	ecs	(?:(?:[0-5]?[0-9]|60)(?:[:.,][0-9]+)?)	grok-patterns
TIME	ecs	(?!<[0-9])%{HOUR}:%{MINUTE}(?::%{SECOND})(?![0-9])	grok-patterns
DATE_US	ecs	%{MONTHNUM}[/-]%{MONTHDAY}[/-]%{YEAR}	grok-patterns
DATE_EU	ecs	%{MONTHDAY}[./-]%{MONTHNUM}[./-]%{YEAR}	grok-patterns
ISO8601_TIMEZONE	ecs	(?:Z|[+-]%{HOUR}(?::?%{MINUTE}))	grok-patterns
ISO8601_SECOND	ecs	%{SECOND}	grok-patterns
TIMESTAMP_ISO8601	ecs	%{YEAR}-%{MONTHNUM}-%{MONTHDAY}[T ]%{HOUR}:?%{MINUTE}(?::?%{SECOND})?%{ISO8601_TIMEZONE}?	grok-patterns
DATE	ecs	%{DATE_US}|%{DATE_EU}	grok-patterns
DATESTAMP	ecs	%{DATE}[- ]%{TIME}	grok-patterns
TZ	ecs	(?:[APMCE][SD]T|UTC)	grok-patterns
DATESTAMP_RFC822	ecs	%{DAY} %{MONTH} %{MONTHDAY} %{YEAR} %{TIME} %{TZ}	grok-patterns
DATESTAMP_RFC2822	ecs	%{DAY}, %{MONTHDAY} %{MONTH} %{YEAR} %{TIME} %{ISO8601_TIMEZONE}	grok-patterns
DATESTAMP_OTHER	ecs	%{DAY} %{MONTH} %{MONTHDAY} %{TIME} %{TZ} %{YEAR}	grok-patterns
DATESTAMP_EVENTLOG	ecs	%{YEAR}%{MONTHNUM2}%{MONTHDAY}%{HOUR}%{MINUTE}%{SECOND}	grok-patterns
SYSLOGTIMESTAMP	ecs	%{MONTH} +%{MONTHDAY} %{TIME}	grok-patterns
PROG	ecs	[\\x21-\\x5a\\x5c\\x5e-\\x7e]+	grok-patterns
SYSLOGPROG	ecs	%{PROG:[process][name]}(?:\\[%{POSINT:[process][pid]:int}\\])?	grok-patterns
SYSLOGHOST	ecs	%{IPORHOST}	grok-patterns
SYSLOGFACILITY	ecs	<%{NONNEGINT:[log][syslog][facility][code]:int}.%{NONNEGINT:[log][syslog][priority]:int}>	grok-patterns
HTTPDATE	ecs	%{MONTHDAY}/%{MONTH}/%{YEAR}:%{TIME} %{INT}	grok-patterns
QS	ecs	%{QUOTEDSTRING}	grok-patterns
SYSLOGBASE	ecs	%{SYSLOGTIMESTAMP:timestamp} (?:%{SYSLOGFACILITY} )?%{SYSLOGHOST:[host][hostname]} %{SYSLOGPROG}:	grok-patterns
LOGLEVEL	ecs	([Aa]lert|ALERT|[Tt]race|TRACE|[Dd]ebug|DEBUG|[Nn]otice|NOTICE|[Ii]nfo?(?:rmation)?|INFO?(?:RMATION)?|[Ww]arn?(?:ing)?|WARN?(?:ING)?|[Ee]rr?(?:or)?|ERR?(?:OR)?|[Cc]rit?(?:ical)?|CRIT?(?:ICAL)?|[Ff]atal|FATAL|[Ss]evere|SEVERE|EMERG(?:ENCY)?|[Ee]merg(?:ency)?)	grok-patterns
HAPROXYTIME	ecs	(?!<[0-9])%{HOUR}:%{MINUTE}(?::%{SECOND})(?![0-9])	haproxy
HAPROXYDATE	ecs	%{MONTHDAY}/%{MONTH}/%{YEAR}:%{HAPROXYTIME}.%{INT}	haproxy
HAPROXYCAPTUREDREQUESTHEADERS	ecs	%{DATA:[haproxy][http][request][captured_headers]}	haproxy
HAPROXYCAPTUREDRESPONSEHEADERS	ecs	%{DATA:[haproxy][http][response][captured_headers]}	haproxy
HAPROXYURI	ecs	(?:%{URIPROTO:[url][scheme]}://)?(?:%{USER:[url][username]}(?::[^@]*)?@)?(?:%{IPORHOST:[url][domain]}(?::%{POSINT:[url][port]:int})?)?(?:%{URIPATH:[url][path]}(?:\\?%{URIQUERY:[url][query]})?)?	haproxy
HAPROXYHTTPREQUESTLINE	ecs	(?:<BADREQ>|(?:%{WORD:[http][request][method]} %{HAPROXYURI:[url][original]}(?: HTTP/%{NUMBER:[http][version]})?))	haproxy
HAPROXYHTTPBASE	ecs	%{IP:[source][address]}:%{INT:[source][port]:int} \\[%{HAPROXYDATE:[haproxy][request_date]}\\] %{NOTSPACE:[haproxy][frontend_name]} %{NOTSPACE:[haproxy][backend_name]}/(?:<NOSRV>|%{NOTSPACE:[haproxy][server_name]}) (?:-1|%{INT:[haproxy][http][request][time_wait_ms]:int})/(?:-1|%{INT:[haproxy][total_waiting_time_ms]:int})/(?:-1|%{INT:[haproxy][connection_wait_time_ms]:int})/(?:-1|%{INT:[haproxy][http][request][time_wait_without_data_ms]:int})/%{NOTSPACE:[haproxy][total_time_ms]} %{INT:[http][response][status_code]:int} %{INT:[source][bytes]:int} (?:-|%{DATA:[haproxy][http][request][captured_cookie]}) (?:-|%{DATA:[haproxy][http][response][captured_cookie]}) %{NOTSPACE:[haproxy][termination_state]} %{INT:[haproxy][connections][active]:int}/%{INT:[haproxy][connections][frontend]:int}/%{INT:[haproxy][connections][backend]:int}/%{INT:[haproxy][connections][server]:int}/%{INT:[haproxy][connections][retries]:int} %{INT:[haproxy][server_queue]:int}/%{INT:[haproxy][backend_queue]:int}(?: \\{%{HAPROXYCAPTUREDREQUESTHEADERS}\\}(?: \\{%{HAPROXYCAPTUREDRESPONSEHEADERS}\\})?)?(?: "%{HAPROXYHTTPREQUESTLINE}"?)?	haproxy
HAPROXYHTTP	ecs	(?:%{SYSLOGTIMESTAMP:timestamp}|%{TIMESTAMP_ISO8601:timestamp}) %{IPORHOST:[host][hostname]} %{SYSLOGPROG}: %{HAPROXYHTTPBASE}	haproxy
HAPROXYTCP	ecs	(?:%{SYSLOGTIMESTAMP:timestamp}|%{TIMESTAMP_ISO8601:timestamp}) %{IPORHOST:[host][hostname]} %{SYSLOGPROG}: %{IP:[source][address]}:%{INT:[source][port]:int} \\[%{HAPROXYDATE:[haproxy][request_date]}\\] %{NOTSPACE:[haproxy][frontend_name]} %{NOTSPACE:[haproxy][backend_name]}/(?:<NOSRV>|%{NOTSPACE:[haproxy][server_name]}) (?:-1|%{INT:[haproxy][total_waiting_time_ms]:int})/(?:-1|%{INT:[haproxy][connection_wait_time_ms]:int})/%{NOTSPACE:[haproxy][total_time_ms]} %{INT:[source][bytes]:int} %{NOTSPACE:[haproxy][termination_state]} %{INT:[haproxy][connections][active]:int}/%{INT:[haproxy][connections][frontend]:int}/%{INT:[haproxy][connections][backend]:int}/%{INT:[haproxy][connections][server]:int}/%{INT:[haproxy][connections][retries]:int} %{INT:[haproxy][server_queue]:int}/%{INT:[haproxy][backend_queue]:int}	haproxy
HTTPDERROR_DATE	ecs	%{DAY} %{MONTH} %{MONTHDAY} %{TIME} %{YEAR}	httpd
HTTPD_COMMONLOG	ecs	%{IPORHOST:[source][address]} (?:-|%{HTTPDUSER:[apache][access][user][identity]}) (?:-|%{HTTPDUSER:[user][name]}) \\[%{HTTPDATE:timestamp}\\] "(?:%{WORD:[http][request][method]} %{NOTSPACE:[url][original]}(?: HTTP/%{NUMBER:[http][version]})?|%{DATA})" (?:-|%{INT:[http][response][status_code]:int}) (?:-|%{INT:[http][response][body][bytes]:int})	httpd
HTTPD_COMBINEDLOG	ecs	%{HTTPD_COMMONLOG} "(?:-|%{DATA:[http][request][referrer]})" "(?:-|%{DATA:[user_agent][original]})"	httpd
HTTPD20_ERRORLOG	ecs	\\[%{HTTPDERROR_DATE:timestamp}\\] \\[%{LOGLEVEL:[log][level]}\\] (?:\\[client %{IPORHOST:[source][address]}\\] )?%{GREEDYDATA:message}	httpd
HTTPD24_ERRORLOG	ecs	\\[%{HTTPDERROR_DATE:timestamp}\\] \\[(?:%{WORD:[apache][error][module]})?:%{LOGLEVEL:[log][level]}\\] \\[pid %{POSINT:[process][pid]:int}(:tid %{INT:[process][thread][id]:int})?\\](?: \\(%{POSINT:[apache][error][proxy][error][code]?}\\)%{DATA:[apache][error][proxy][error][message]}:)?(?: \\[client %{IPORHOST:[source][address]}(?::%{POSINT:[source][port]:int})?\\])?(?: %{DATA:[error][code]}:)? %{GREEDYDATA:message}	httpd
HTTPD_ERRORLOG	ecs	%{HTTPD20_ERRORLOG}|%{HTTPD24_ERRORLOG}	httpd
COMMONAPACHELOG	ecs	%{HTTPD_COMMONLOG}	httpd
COMBINEDAPACHELOG	ecs	%{HTTPD_COMBINEDLOG}	httpd
JAVACLASS	ecs	(?:[a-zA-Z$_][a-zA-Z$_0-9]*\\.)*[a-zA-Z$_][a-zA-Z$_0-9]*	java
JAVAFILE	ecs	(?:[a-zA-Z$_0-9. -]+)	java
JAVAMETHOD	ecs	(?:(<(?:cl)?init>)|[a-zA-Z$_][a-zA-Z$_0-9]*)	java
JAVASTACKTRACEPART	ecs	%{SPACE}at %{JAVACLASS:[java][log][origin][class][name]}\\.%{JAVAMETHOD:[log][origin][function]}\\(%{JAVAFILE:[log][origin][file][name]}(?::%{INT:[log][origin][file][line]:int})?\\)	java
JAVATHREAD	ecs	(?:[A-Z]{2}-Processor[\\d]+)	java
JAVALOGMESSAGE	ecs	(?:.*)	java
CATALINA7_DATESTAMP	ecs	%{MONTH} %{MONTHDAY}, %{YEAR} %{HOUR}:%{MINUTE}:%{SECOND} (?:AM|PM)	java
CATALINA7_LOG	ecs	%{CATALINA7_DATESTAMP:timestamp} %{JAVACLASS:[java][log][origin][class][name]}(?: %{JAVAMETHOD:[log][origin][function]})?\\s*(?:%{LOGLEVEL:[log][level]}:)? %{JAVALOGMESSAGE:message}	java
CATALINA8_DATESTAMP	ecs	%{MONTHDAY}-%{MONTH}-%{YEAR} %{HOUR}:%{MINUTE}:%{SECOND}	java
BIND9	ecs	%{BIND9_QUERYLOG}	bind
BRO_BOOL	ecs	[TF]	bro
CATALINA8_LOG	ecs	%{CATALINA8_DATESTAMP:timestamp} %{LOGLEVEL:[log][level]} \\[%{DATA:[java][log][origin][thread][name]}\\] %{JAVACLASS:[java][log][origin][class][name]}\\.(?:%{JAVAMETHOD:[log][origin][function]})? %{JAVALOGMESSAGE:message}	java
CATALINA_DATESTAMP	ecs	(?:%{CATALINA8_DATESTAMP})|(?:%{CATALINA7_DATESTAMP})	java
CATALINALOG	ecs	(?:%{CATALINA8_LOG})|(?:%{CATALINA7_LOG})	java
TOMCAT7_LOG	ecs	%{CATALINA7_LOG}	java
TOMCAT8_LOG	ecs	%{CATALINA8_LOG}	java
TOMCATLEGACY_DATESTAMP	ecs	%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{HOUR}:%{MINUTE}:%{SECOND}(?: %{ISO8601_TIMEZONE})?	java
TOMCATLEGACY_LOG	ecs	%{TOMCATLEGACY_DATESTAMP:timestamp} \\| %{LOGLEVEL:[log][level]} \\| %{JAVACLASS:[java][log][origin][class][name]} - %{JAVALOGMESSAGE:message}	java
TOMCAT_DATESTAMP	ecs	(?:%{CATALINA8_DATESTAMP})|(?:%{CATALINA7_DATESTAMP})|(?:%{TOMCATLEGACY_DATESTAMP})	java
TOMCATLOG	ecs	(?:%{TOMCAT8_LOG})|(?:%{TOMCAT7_LOG})|(?:%{TOMCATLEGACY_LOG})	java
RT_FLOW_TAG	ecs	(?:RT_FLOW_SESSION_CREATE|RT_FLOW_SESSION_CLOSE|RT_FLOW_SESSION_DENY)	junos
RT_FLOW_EVENT	ecs	RT_FLOW_TAG	junos
RT_FLOW1	ecs	%{RT_FLOW_TAG:[juniper][srx][tag]}: %{GREEDYDATA:[juniper][srx][reason]}: %{IP:[source][ip]}/%{INT:[source][port]:int}->%{IP:[destination][ip]}/%{INT:[destination][port]:int} %{DATA:[juniper][srx][service_name]} %{IP:[source][nat][ip]}/%{INT:[source][nat][port]:int}->%{IP:[destination][nat][ip]}/%{INT:[destination][nat][port]:int} (?:(?:None)|(?:%{DATA:[juniper][srx][src_nat_rule_name]})) (?:(?:None)|(?:%{DATA:[juniper][srx][dst_nat_rule_name]})) %{INT:[network][iana_number]} %{DATA:[rule][name]} %{DATA:[observer][ingress][zone]} %{DATA:[observer][egress][zone]} %{INT:[juniper][srx][session_id]} \\d+\\(%{INT:[source][bytes]:int}\\) \\d+\\(%{INT:[destination][bytes]:int}\\) %{INT:[juniper][srx][elapsed_time]:int} .*	junos
RT_FLOW2	ecs	%{RT_FLOW_TAG:[juniper][srx][tag]}: session created %{IP:[source][ip]}/%{INT:[source][port]:int}->%{IP:[destination][ip]}/%{INT:[destination][port]:int} %{DATA:[juniper][srx][service_name]} %{IP:[source][nat][ip]}/%{INT:[source][nat][port]:int}->%{IP:[destination][nat][ip]}/%{INT:[destination][nat][port]:int} (?:(?:None)|(?:%{DATA:[juniper][srx][src_nat_rule_name]})) (?:(?:None)|(?:%{DATA:[juniper][srx][dst_nat_rule_name]})) %{INT:[network][iana_number]} %{DATA:[rule][name]} %{DATA:[observer][ingress][zone]} %{DATA:[observer][egress][zone]} %{INT:[juniper][srx][session_id]} .*	junos
RT_FLOW3	ecs	%{RT_FLOW_TAG:[juniper][srx][tag]}: session denied %{IP:[source][ip]}/%{INT:[source][port]:int}->%{IP:[destination][ip]}/%{INT:[destination][port]:int} %{DATA:[juniper][srx][service_name]} %{INT:[network][iana_number]}\\(\\d\\) %{DATA:[rule][name]} %{DATA:[observer][ingress][zone]} %{DATA:[observer][egress][zone]} .*	junos
SYSLOGBASE2	ecs	(?:%{SYSLOGTIMESTAMP:timestamp}|%{TIMESTAMP_ISO8601:timestamp})(?: %{SYSLOGFACILITY})?(?: %{SYSLOGHOST:[host][hostname]})?(?: %{SYSLOGPROG}:)?	linux-syslog
SYSLOGPAMSESSION	ecs	%{SYSLOGBASE} (?=%{GREEDYDATA:message})%{WORD:[system][auth][pam][module]}\\(%{DATA:[system][auth][pam][origin]}\\): session %{WORD:[system][auth][pam][session_state]} for user %{USERNAME:[user][name]}(?: by %{GREEDYDATA})?	linux-syslog
CRONLOG	ecs	%{SYSLOGBASE} \\(%{USER:[user][name]}\\) %{CRON_ACTION:[system][cron][action]} \\(%{DATA:message}\\)	linux-syslog
SYSLOGLINE	ecs	%{SYSLOGBASE2} %{GREEDYDATA:message}	linux-syslog
SYSLOG5424PRI	ecs	<%{NONNEGINT:[log][syslog][priority]:int}>	linux-syslog
SYSLOG5424SD	ecs	\\[%{DATA}\\]+	linux-syslog
SYSLOG5424BASE	ecs	%{SYSLOG5424PRI}%{NONNEGINT:[system][syslog][version]} +(?:-|%{TIMESTAMP_ISO8601:timestamp}) +(?:-|%{IPORHOST:[host][hostname]}) +(?:-|%{SYSLOG5424PRINTASCII:[process][name]}) +(?:-|%{POSINT:[process][pid]:int}) +(?:-|%{SYSLOG5424PRINTASCII:[event][code]}) +(?:-|%{SYSLOG5424SD:[system][syslog][structured_data]})?	linux-syslog
SYSLOG5424LINE	ecs	%{SYSLOG5424BASE} +%{GREEDYDATA:message}	linux-syslog
MAVEN_VERSION	ecs	(?:(\\d+)\\.)?(?:(\\d+)\\.)?(\\*|\\d+)(?:[.-](RELEASE|SNAPSHOT))?	maven
MCOLLECTIVE	ecs	., \\[%{TIMESTAMP_ISO8601:timestamp} #%{POSINT:[process][pid]:int}\\]%{SPACE}%{LOGLEVEL:[log][level]}	mcollective
MCOLLECTIVEAUDIT	ecs	%{TIMESTAMP_ISO8601:timestamp}:	mcollective
MONGO_LOG	ecs	%{SYSLOGTIMESTAMP:timestamp} \\[%{WORD:[mongodb][component]}\\] %{GREEDYDATA:message}	mongodb
MONGO_QUERY	ecs	\\{ (?<={ ).*(?= } ntoreturn:) \\}	mongodb
MONGO_SLOWQUERY	ecs	%{WORD:[mongodb][profile][op]} %{MONGO_WORDDASH:[mongodb][database]}\\.%{MONGO_WORDDASH:[mongodb][collection]} %{WORD}: %{MONGO_QUERY:[mongodb][query][original]} ntoreturn:%{NONNEGINT:[mongodb][profile][ntoreturn]:int} ntoskip:%{NONNEGINT:[mongodb][profile][ntoskip]:int} nscanned:%{NONNEGINT:[mongodb][profile][nscanned]:int}.*? nreturned:%{NONNEGINT:[mongodb][profile][nreturned]:int}.*? %{INT:[mongodb][profile][duration]:int}ms	mongodb
MONGO_WORDDASH	ecs	\\b[\\w-]+\\b	mongodb
MONGO3_SEVERITY	ecs	\\w	mongodb
MONGO3_COMPONENT	ecs	%{WORD}	mongodb
MONGO3_LOG	ecs	%{TIMESTAMP_ISO8601:timestamp} %{MONGO3_SEVERITY:[log][level]} (?:-|%{MONGO3_COMPONENT:[mongodb][component]})%{SPACE}(?:\\[%{DATA:[mongodb][context]}\\])? %{GREEDYDATA:message}	mongodb
NAGIOSTIME	ecs	\\[%{NUMBER:timestamp}\\]	nagios
NAGIOS_TYPE_CURRENT_SERVICE_STATE	ecs	CURRENT SERVICE STATE	nagios
NAGIOS_TYPE_CURRENT_HOST_STATE	ecs	CURRENT HOST STATE	nagios
NAGIOS_TYPE_SERVICE_NOTIFICATION	ecs	SERVICE NOTIFICATION	nagios
NAGIOS_TYPE_HOST_NOTIFICATION	ecs	HOST NOTIFICATION	nagios
NAGIOS_TYPE_SERVICE_ALERT	ecs	SERVICE ALERT	nagios
NAGIOS_TYPE_HOST_ALERT	ecs	HOST ALERT	nagios
NAGIOS_TYPE_SERVICE_FLAPPING_ALERT	ecs	SERVICE FLAPPING ALERT	nagios
NAGIOS_TYPE_HOST_FLAPPING_ALERT	ecs	HOST FLAPPING ALERT	nagios
NAGIOS_TYPE_SERVICE_DOWNTIME_ALERT	ecs	SERVICE DOWNTIME ALERT	nagios
NAGIOS_TYPE_HOST_DOWNTIME_ALERT	ecs	HOST DOWNTIME ALERT	nagios
NAGIOS_TYPE_PASSIVE_SERVICE_CHECK	ecs	PASSIVE SERVICE CHECK	nagios
NAGIOS_TYPE_PASSIVE_HOST_CHECK	ecs	PASSIVE HOST CHECK	nagios
NAGIOS_TYPE_SERVICE_EVENT_HANDLER	ecs	SERVICE EVENT HANDLER	nagios
NAGIOS_TYPE_HOST_EVENT_HANDLER	ecs	HOST EVENT HANDLER	nagios
NAGIOS_TYPE_EXTERNAL_COMMAND	ecs	EXTERNAL COMMAND	nagios
NAGIOS_TYPE_TIMEPERIOD_TRANSITION	ecs	TIMEPERIOD TRANSITION	nagios
NAGIOS_EC_DISABLE_SVC_CHECK	ecs	DISABLE_SVC_CHECK	nagios
NAGIOS_EC_ENABLE_SVC_CHECK	ecs	ENABLE_SVC_CHECK	nagios
NAGIOS_EC_DISABLE_HOST_CHECK	ecs	DISABLE_HOST_CHECK	nagios
NAGIOS_EC_ENABLE_HOST_CHECK	ecs	ENABLE_HOST_CHECK	nagios
NAGIOS_EC_PROCESS_SERVICE_CHECK_RESULT	ecs	PROCESS_SERVICE_CHECK_RESULT	nagios
NAGIOS_EC_PROCESS_HOST_CHECK_RESULT	ecs	PROCESS_HOST_CHECK_RESULT	nagios
NAGIOS_EC_SCHEDULE_SERVICE_DOWNTIME	ecs	SCHEDULE_SERVICE_DOWNTIME	nagios
NAGIOS_EC_SCHEDULE_HOST_DOWNTIME	ecs	SCHEDULE_HOST_DOWNTIME	nagios
NAGIOS_EC_DISABLE_HOST_SVC_NOTIFICATIONS	ecs	DISABLE_HOST_SVC_NOTIFICATIONS	nagios
NAGIOS_EC_ENABLE_HOST_SVC_NOTIFICATIONS	ecs	ENABLE_HOST_SVC_NOTIFICATIONS	nagios
NAGIOS_EC_DISABLE_HOST_NOTIFICATIONS	ecs	DISABLE_HOST_NOTIFICATIONS	nagios
NAGIOS_EC_ENABLE_HOST_NOTIFICATIONS	ecs	ENABLE_HOST_NOTIFICATIONS	nagios
NAGIOS_EC_DISABLE_SVC_NOTIFICATIONS	ecs	DISABLE_SVC_NOTIFICATIONS	nagios
NAGIOS_EC_ENABLE_SVC_NOTIFICATIONS	ecs	ENABLE_SVC_NOTIFICATIONS	nagios
NAGIOS_WARNING	ecs	Warning:%{SPACE}%{GREEDYDATA:message}	nagios
NAGIOS_CURRENT_SERVICE_STATE	ecs	%{NAGIOS_TYPE_CURRENT_SERVICE_STATE:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{INT:[nagios][log][attempt]:int};%{GREEDYDATA:message}	nagios
NAGIOS_CURRENT_HOST_STATE	ecs	%{NAGIOS_TYPE_CURRENT_HOST_STATE:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{INT:[nagios][log][attempt]:int};%{GREEDYDATA:message}	nagios
NAGIOS_SERVICE_NOTIFICATION	ecs	%{NAGIOS_TYPE_SERVICE_NOTIFICATION:[nagios][log][type]}: %{DATA:[user][name]};%{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{DATA:[nagios][log][notification_command]};%{GREEDYDATA:message}	nagios
NAGIOS_HOST_NOTIFICATION	ecs	%{NAGIOS_TYPE_HOST_NOTIFICATION:[nagios][log][type]}: %{DATA:[user][name]};%{DATA:[host][hostname]};%{DATA:[service][state]};%{DATA:[nagios][log][notification_command]};%{GREEDYDATA:message}	nagios
NAGIOS_SERVICE_ALERT	ecs	%{NAGIOS_TYPE_SERVICE_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{INT:[nagios][log][attempt]:int};%{GREEDYDATA:message}	nagios
NAGIOS_SERVICE_FLAPPING_ALERT	ecs	%{NAGIOS_TYPE_SERVICE_FLAPPING_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{GREEDYDATA:message}	nagios
NAGIOS_HOST_FLAPPING_ALERT	ecs	%{NAGIOS_TYPE_HOST_FLAPPING_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{GREEDYDATA:message}	nagios
NAGIOS_SERVICE_DOWNTIME_ALERT	ecs	%{NAGIOS_TYPE_SERVICE_DOWNTIME_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][comment]}	nagios
NAGIOS_HOST_DOWNTIME_ALERT	ecs	%{NAGIOS_TYPE_HOST_DOWNTIME_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][comment]}	nagios
NAGIOS_PASSIVE_SERVICE_CHECK	ecs	%{NAGIOS_TYPE_PASSIVE_SERVICE_CHECK:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][comment]}	nagios
NAGIOS_PASSIVE_HOST_CHECK	ecs	%{NAGIOS_TYPE_PASSIVE_HOST_CHECK:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][comment]}	nagios
NAGIOS_SERVICE_EVENT_HANDLER	ecs	%{NAGIOS_TYPE_SERVICE_EVENT_HANDLER:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{DATA:[nagios][log][event_handler_name]}	nagios
NAGIOS_HOST_EVENT_HANDLER	ecs	%{NAGIOS_TYPE_HOST_EVENT_HANDLER:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{DATA:[nagios][log][event_handler_name]}	nagios
NAGIOS_TIMEPERIOD_TRANSITION	ecs	%{NAGIOS_TYPE_TIMEPERIOD_TRANSITION:[nagios][log][type]}: %{DATA:[service][name]};%{NUMBER:[nagios][log][period_from]:int};%{NUMBER:[nagios][log][period_to]:int}	nagios
NAGIOS_EC_LINE_DISABLE_SVC_CHECK	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_DISABLE_SVC_CHECK:[nagios][log][command]};%{DATA:[host][hostname]};%{DATA:[service][name]}	nagios
NAGIOS_EC_LINE_DISABLE_HOST_CHECK	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_DISABLE_HOST_CHECK:[nagios][log][command]};%{DATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_ENABLE_SVC_CHECK	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_ENABLE_SVC_CHECK:[nagios][log][command]};%{DATA:[host][hostname]};%{DATA:[service][name]}	nagios
NAGIOS_EC_LINE_ENABLE_HOST_CHECK	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_ENABLE_HOST_CHECK:[nagios][log][command]};%{DATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_PROCESS_SERVICE_CHECK_RESULT	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_PROCESS_SERVICE_CHECK_RESULT:[nagios][log][command]};%{DATA:[host][hostname]};%{DATA:[service][name]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][check_result]}	nagios
NAGIOS_EC_LINE_PROCESS_HOST_CHECK_RESULT	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_PROCESS_HOST_CHECK_RESULT:[nagios][log][command]};%{DATA:[host][hostname]};%{DATA:[service][state]};%{GREEDYDATA:[nagios][log][check_result]}	nagios
NAGIOS_EC_LINE_DISABLE_HOST_SVC_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_DISABLE_HOST_SVC_NOTIFICATIONS:[nagios][log][command]};%{GREEDYDATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_DISABLE_HOST_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_DISABLE_HOST_NOTIFICATIONS:[nagios][log][command]};%{GREEDYDATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_DISABLE_SVC_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_DISABLE_SVC_NOTIFICATIONS:[nagios][log][command]};%{DATA:[host][hostname]};%{GREEDYDATA:[service][name]}	nagios
NAGIOS_EC_LINE_ENABLE_HOST_SVC_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_ENABLE_HOST_SVC_NOTIFICATIONS:[nagios][log][command]};%{GREEDYDATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_ENABLE_HOST_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_ENABLE_HOST_NOTIFICATIONS:[nagios][log][command]};%{GREEDYDATA:[host][hostname]}	nagios
NAGIOS_EC_LINE_ENABLE_SVC_NOTIFICATIONS	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_ENABLE_SVC_NOTIFICATIONS:[nagios][log][command]};%{DATA:[host][hostname]};%{GREEDYDATA:[service][name]}	nagios
BRO_DATA	ecs	[^\\t]+	bro
CISCO_INTERVAL	ecs	first hit|%{INT}-second interval	firewalls
NAGIOS_EC_LINE_SCHEDULE_HOST_DOWNTIME	ecs	%{NAGIOS_TYPE_EXTERNAL_COMMAND:[nagios][log][type]}: %{NAGIOS_EC_SCHEDULE_HOST_DOWNTIME:[nagios][log][command]};%{DATA:[host][hostname]};%{NUMBER:[nagios][log][start_time]};%{NUMBER:[nagios][log][end_time]};%{NUMBER:[nagios][log][fixed]};%{NUMBER:[nagios][log][trigger_id]};%{NUMBER:[nagios][log][duration]:int};%{DATA:[user][name]};%{DATA:[nagios][log][comment]}	nagios
NAGIOSLOGLINE	ecs	%{NAGIOSTIME} (?:%{NAGIOS_WARNING}|%{NAGIOS_CURRENT_SERVICE_STATE}|%{NAGIOS_CURRENT_HOST_STATE}|%{NAGIOS_SERVICE_NOTIFICATION}|%{NAGIOS_HOST_NOTIFICATION}|%{NAGIOS_SERVICE_ALERT}|%{NAGIOS_HOST_ALERT}|%{NAGIOS_SERVICE_FLAPPING_ALERT}|%{NAGIOS_HOST_FLAPPING_ALERT}|%{NAGIOS_SERVICE_DOWNTIME_ALERT}|%{NAGIOS_HOST_DOWNTIME_ALERT}|%{NAGIOS_PASSIVE_SERVICE_CHECK}|%{NAGIOS_PASSIVE_HOST_CHECK}|%{NAGIOS_SERVICE_EVENT_HANDLER}|%{NAGIOS_HOST_EVENT_HANDLER}|%{NAGIOS_TIMEPERIOD_TRANSITION}|%{NAGIOS_EC_LINE_DISABLE_SVC_CHECK}|%{NAGIOS_EC_LINE_ENABLE_SVC_CHECK}|%{NAGIOS_EC_LINE_DISABLE_HOST_CHECK}|%{NAGIOS_EC_LINE_ENABLE_HOST_CHECK}|%{NAGIOS_EC_LINE_PROCESS_HOST_CHECK_RESULT}|%{NAGIOS_EC_LINE_PROCESS_SERVICE_CHECK_RESULT}|%{NAGIOS_EC_LINE_SCHEDULE_HOST_DOWNTIME}|%{NAGIOS_EC_LINE_DISABLE_HOST_SVC_NOTIFICATIONS}|%{NAGIOS_EC_LINE_ENABLE_HOST_SVC_NOTIFICATIONS}|%{NAGIOS_EC_LINE_DISABLE_HOST_NOTIFICATIONS}|%{NAGIOS_EC_LINE_ENABLE_HOST_NOTIFICATIONS}|%{NAGIOS_EC_LINE_DISABLE_SVC_NOTIFICATIONS}|%{NAGIOS_EC_LINE_ENABLE_SVC_NOTIFICATIONS})	nagios
POSTGRESQL	ecs	%{DATESTAMP:timestamp} %{TZ:[event][timezone]} %{DATA:[user][name]} %{GREEDYDATA:[postgresql][log][connection_id]} %{POSINT:[process][pid]:int}	postgresql
RUUID	ecs	\\h{32}	rails
RCONTROLLER	ecs	(?<[rails][controller][class]>[^#]+)#(?<[rails][controller][action]>\\w+)	rails
RAILS3HEAD	ecs	(?m)Started %{WORD:[http][request][method]} "%{URIPATHPARAM:[url][original]}" for %{IPORHOST:[source][address]} at (?<timestamp>%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{HOUR}:%{MINUTE}:%{SECOND} %{ISO8601_TIMEZONE})	rails
RPROCESSING	ecs	\\W*Processing by %{RCONTROLLER} as (?<[rails][request][format]>\\S+)(?:\\W*Parameters: {%{DATA:[rails][request][params]}}\\W*)?	rails
RAILS3FOOT	ecs	Completed %{POSINT:[http][response][status_code]:int}%{DATA} in %{NUMBER:[rails][request][duration][total]:float}ms %{RAILS3PROFILE}%{GREEDYDATA}	rails
ZEEK_HTTP	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{INT:[zeek][http][trans_depth]:int}\\t(?:-|%{WORD:[http][request][method]})\\t(?:-|%{ZEEK_DATA:[url][domain]})\\t(?:-|%{ZEEK_DATA:[url][original]})\\t(?:-|%{ZEEK_DATA:[http][request][referrer]})\\t(?:-|%{NUMBER:[http][version]})\\t(?:-|%{ZEEK_DATA:[user_agent][original]})\\t(?:-|%{ZEEK_DATA:[zeek][http][origin]})\\t(?:-|%{NUMBER:[http][request][body][bytes]:int})\\t(?:-|%{NUMBER:[http][response][body][bytes]:int})\\t(?:-|%{POSINT:[http][response][status_code]:int})\\t(?:-|%{DATA:[zeek][http][status_msg]})\\t(?:-|%{POSINT:[zeek][http][info_code]:int})\\t(?:-|%{DATA:[zeek][http][info_msg]})\\t(?:\\(empty\\)|%{ZEEK_DATA:[zeek][http][tags]})\\t(?:-|%{ZEEK_DATA:[url][username]})\\t(?:-|%{ZEEK_DATA:[url][password]})\\t(?:-|%{ZEEK_DATA:[zeek][http][proxied]})\\t(?:-|%{ZEEK_DATA:[zeek][http][orig_fuids]})\\t(?:-|%{ZEEK_DATA:[zeek][http][orig_filenames]})\\t(?:-|%{ZEEK_DATA:[http][request][mime_type]})\\t(?:-|%{ZEEK_DATA:[zeek][http][resp_fuids]})\\t(?:-|%{ZEEK_DATA:[zeek][http][resp_filenames]})\\t(?:-|%{ZEEK_DATA:[http][response][mime_type]})	zeek
ZEEK_DNS	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{WORD:[network][transport]}\\t(?:-|%{INT:[dns][id]:int})\\t(?:-|%{NUMBER:[zeek][dns][rtt]:float})\\t(?:-|%{ZEEK_DATA:[dns][question][name]})\\t(?:-|%{INT:[zeek][dns][qclass]:int})\\t(?:-|%{ZEEK_DATA:[zeek][dns][qclass_name]})\\t(?:-|%{INT:[zeek][dns][qtype]:int})\\t(?:-|%{ZEEK_DATA:[dns][question][type]})\\t(?:-|%{INT:[zeek][dns][rcode]:int})\\t(?:-|%{ZEEK_DATA:[dns][response_code]})\\t%{ZEEK_BOOL:[zeek][dns][AA]}\\t%{ZEEK_BOOL:[zeek][dns][TC]}\\t%{ZEEK_BOOL:[zeek][dns][RD]}\\t%{ZEEK_BOOL:[zeek][dns][RA]}\\t%{NONNEGINT:[zeek][dns][Z]:int}\\t(?:-|%{ZEEK_DATA:[zeek][dns][answers]})\\t(?:-|%{DATA:[zeek][dns][TTLs]})\\t(?:-|%{ZEEK_BOOL:[zeek][dns][rejected]})	zeek
ZEEK_CONN	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][session_id]}\\t%{IP:[source][ip]}\\t%{INT:[source][port]:int}\\t%{IP:[destination][ip]}\\t%{INT:[destination][port]:int}\\t%{WORD:[network][transport]}\\t(?:-|%{ZEEK_DATA:[network][protocol]})\\t(?:-|%{NUMBER:[zeek][connection][duration]:float})\\t(?:-|%{INT:[zeek][connection][orig_bytes]:int})\\t(?:-|%{INT:[zeek][connection][resp_bytes]:int})\\t(?:-|%{ZEEK_DATA:[zeek][connection][state]})\\t(?:-|%{ZEEK_BOOL:[zeek][connection][local_orig]})\\t(?:-|%{ZEEK_BOOL:[zeek][connection][local_resp]})\\t(?:-|%{INT:[zeek][connection][missed_bytes]:int})\\t(?:-|%{ZEEK_DATA:[zeek][connection][history]})\\t(?:-|%{INT:[source][packets]:int})\\t(?:-|%{INT:[source][bytes]:int})\\t(?:-|%{INT:[destination][packets]:int})\\t(?:-|%{INT:[destination][bytes]:int})\\t(?:-|%{ZEEK_DATA:[zeek][connection][tunnel_parents]})(?:\\t(?:-|%{COMMONMAC:[source][mac]})\\t(?:-|%{COMMONMAC:[destination][mac]}))?	zeek
ZEEK_FILES_TX_HOSTS	ecs	(?:-|%{IP:[server][ip]})|(?<[zeek][files][tx_hosts]>%{IP:[server][ip]}(?:[\\s,]%{IP})+)	zeek
ZEEK_FILES_RX_HOSTS	ecs	(?:-|%{IP:[client][ip]})|(?<[zeek][files][rx_hosts]>%{IP:[client][ip]}(?:[\\s,]%{IP})+)	zeek
ZEEK_FILES	ecs	%{NUMBER:timestamp}\\t%{NOTSPACE:[zeek][files][fuid]}\\t%{ZEEK_FILES_TX_HOSTS}\\t%{ZEEK_FILES_RX_HOSTS}\\t(?:-|%{ZEEK_DATA:[zeek][files][session_ids]})\\t(?:-|%{ZEEK_DATA:[zeek][files][source]})\\t(?:-|%{INT:[zeek][files][depth]:int})\\t(?:-|%{ZEEK_DATA:[zeek][files][analyzers]})\\t(?:-|%{ZEEK_DATA:[file][mime_type]})\\t(?:-|%{ZEEK_DATA:[file][name]})\\t(?:-|%{NUMBER:[zeek][files][duration]:float})\\t(?:-|%{ZEEK_DATA:[zeek][files][local_orig]})\\t(?:-|%{ZEEK_BOOL:[zeek][files][is_orig]})\\t(?:-|%{INT:[zeek][files][seen_bytes]:int})\\t(?:-|%{INT:[file][size]:int})\\t(?:-|%{INT:[zeek][files][missing_bytes]:int})\\t(?:-|%{INT:[zeek][files][overflow_bytes]:int})\\t(?:-|%{ZEEK_BOOL:[zeek][files][timedout]})\\t(?:-|%{ZEEK_DATA:[zeek][files][parent_fuid]})\\t(?:-|%{ZEEK_DATA:[file][hash][md5]})\\t(?:-|%{ZEEK_DATA:[file][hash][sha1]})\\t(?:-|%{ZEEK_DATA:[file][hash][sha256]})\\t(?:-|%{ZEEK_DATA:[zeek][files][extracted]})(?:\\t(?:-|%{ZEEK_BOOL:[zeek][files][extracted_cutoff]})\\t(?:-|%{INT:[zeek][files][extracted_size]:int}))?	zeek
S3_REQUEST_LINE	ecs	(?:%{WORD:[http][request][method]} %{NOTSPACE:[url][original]}(?: HTTP/%{NUMBER:[http][version]})?)	aws
S3_ACCESS_LOG	ecs	%{WORD:[aws][s3access][bucket_owner]} %{NOTSPACE:[aws][s3access][bucket]} \\[%{HTTPDATE:timestamp}\\] (?:-|%{IP:[client][ip]}) (?:-|%{NOTSPACE:[client][user][id]}) %{NOTSPACE:[aws][s3access][request_id]} %{NOTSPACE:[aws][s3access][operation]} (?:-|%{NOTSPACE:[aws][s3access][key]}) (?:-|"%{S3_REQUEST_LINE:[aws][s3access][request_uri]}") (?:-|%{INT:[http][response][status_code]:int}) (?:-|%{NOTSPACE:[aws][s3access][error_code]}) (?:-|%{INT:[aws][s3access][bytes_sent]:int}) (?:-|%{INT:[aws][s3access][object_size]:int}) (?:-|%{INT:[aws][s3access][total_time]:int}) (?:-|%{INT:[aws][s3access][turn_around_time]:int}) "(?:-|%{DATA:[http][request][referrer]})" "(?:-|%{DATA:[user_agent][original]})" (?:-|%{NOTSPACE:[aws][s3access][version_id]})(?: (?:-|%{NOTSPACE:[aws][s3access][host_id]}) (?:-|%{NOTSPACE:[aws][s3access][signature_version]}) (?:-|%{NOTSPACE:[tls][cipher]}) (?:-|%{NOTSPACE:[aws][s3access][authentication_type]}) (?:-|%{NOTSPACE:[aws][s3access][host_header]}) (?:-|%{NOTSPACE:[aws][s3access][tls_version]}))?	aws
ELB_URIHOST	ecs	%{IPORHOST:[url][domain]}(?::%{POSINT:[url][port]:int})?	aws
ELB_URIPATHQUERY	ecs	%{URIPATH:[url][path]}(?:\\?%{URIQUERY:[url][query]})?	aws
ELB_URIPATHPARAM	ecs	%{ELB_URIPATHQUERY}	aws
ELB_URI	ecs	%{URIPROTO:[url][scheme]}://(?:%{USER:[url][username]}(?::[^@]*)?@)?(?:%{ELB_URIHOST})?(?:%{ELB_URIPATHQUERY})?	aws
ELB_REQUEST_LINE	ecs	(?:%{WORD:[http][request][method]} %{ELB_URI:[url][original]}(?: HTTP/%{NUMBER:[http][version]})?)	aws
ELB_V1_HTTP_LOG	ecs	%{TIMESTAMP_ISO8601:timestamp} %{NOTSPACE:[aws][elb][name]} %{IP:[source][ip]}:%{INT:[source][port]:int} (?:-|(?:%{IP:[aws][elb][backend][ip]}:%{INT:[aws][elb][backend][port]:int})) (?:-1|%{NUMBER:[aws][elb][request_processing_time][sec]:float}) (?:-1|%{NUMBER:[aws][elb][backend_processing_time][sec]:float}) (?:-1|%{NUMBER:[aws][elb][response_processing_time][sec]:float}) %{INT:[http][response][status_code]:int} (?:-|%{INT:[aws][elb][backend][http][response][status_code]:int}) %{INT:[http][request][body][bytes]:int} %{INT:[http][response][body][bytes]:int} "%{ELB_REQUEST_LINE}"(?: "(?:-|%{DATA:[user_agent][original]})" (?:-|%{NOTSPACE:[tls][cipher]}) (?:-|%{NOTSPACE:[aws][elb][ssl_protocol]}))?	aws
ELB_ACCESS_LOG	ecs	%{ELB_V1_HTTP_LOG}	aws
CLOUDFRONT_EDGE_LOCATION	ecs	[A-Z]{3}[0-9]{1,2}(?:-[A-Z0-9]{2})?	aws
BACULA_TIMESTAMP	ecs	%{MONTHDAY}-%{MONTH}(?:-%{YEAR})? %{HOUR}:%{MINUTE}	bacula
BACULA_HOST	ecs	%{HOSTNAME}	bacula
BACULA_VOLUME	ecs	%{USER}	bacula
BACULA_DEVICE	ecs	%{USER}	bacula
BACULA_DEVICEPATH	ecs	%{UNIXPATH}	bacula
SPACE	ecs	\\s*	grok-patterns
DATA	ecs	.*?	grok-patterns
HTTPDUSER	ecs	%{EMAILADDRESS}|%{USER}	httpd
SYSLOG5424PRINTASCII	ecs	[!-~]+	linux-syslog
CRON_ACTION	ecs	[A-Z ]+	linux-syslog
NAGIOS_HOST_ALERT	ecs	%{NAGIOS_TYPE_HOST_ALERT:[nagios][log][type]}: %{DATA:[host][hostname]};%{DATA:[service][state]};%{DATA:[nagios][log][state_type]};%{INT:[nagios][log][attempt]:int};%{GREEDYDATA:message}	nagios
RAILS3PROFILE	ecs	(?:\\(Views: %{NUMBER:[rails][request][duration][view]:float}ms \\| ActiveRecord: %{NUMBER:[rails][request][duration][active_record]:float}ms|\\(ActiveRecord: %{NUMBER:[rails][request][duration][active_record]:float}ms)?	rails
RAILS3	ecs	%{RAILS3HEAD}(?:%{RPROCESSING})?(?<[rails][request][explain][original]>(?:%{DATA}\\n)*)(?:%{RAILS3FOOT})?	rails
REDISTIMESTAMP	ecs	%{MONTHDAY} %{MONTH} %{TIME}	redis
REDISLOG	ecs	\\[%{POSINT:[process][pid]:int}\\] %{REDISTIMESTAMP:timestamp} \\*	redis
REDISMONLOG	ecs	%{NUMBER:timestamp} \\[%{INT:[redis][database][id]} %{IP:[client][ip]}:%{POSINT:[client][port]:int}\\] "%{WORD:[redis][command][name]}"\\s?%{GREEDYDATA:[redis][command][args]}	redis
RUBY_LOGLEVEL	ecs	(?:DEBUG|FATAL|ERROR|WARN|INFO)	ruby
RUBY_LOGGER	ecs	[DFEWI], \\[%{TIMESTAMP_ISO8601:timestamp} #%{POSINT:[process][pid]:int}\\] *%{RUBY_LOGLEVEL:[log][level]} -- +%{DATA:[process][name]}: %{GREEDYDATA:message}	ruby
SQUID3_STATUS	ecs	(?:%{POSINT:[http][response][status_code]:int}|0|000)	squid
SQUID3	ecs	%{NUMBER:timestamp}\\s+%{NUMBER:[squid][request][duration]:int}\\s%{IP:[source][ip]}\\s%{WORD:[event][action]}/%{SQUID3_STATUS}\\s%{INT:[http][response][bytes]:int}\\s%{WORD:[http][request][method]}\\s%{NOTSPACE:[url][original]}\\s(?:-|%{NOTSPACE:[user][name]})\\s%{WORD:[squid][hierarchy_code]}/(?:-|%{IPORHOST:[destination][address]})\\s(?:-|%{NOTSPACE:[http][response][mime_type]})	squid
ZEEK_BOOL	ecs	[TF]	zeek
ZEEK_DATA	ecs	[^\\t]+	zeek
\.


--
-- Data for Name: fda_grokpatterncategory; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_grokpatterncategory (id, type) FROM stdin;
aws	ecs
bacula	ecs
bind	ecs
bro	ecs
exim	ecs
firewalls	ecs
grok-patterns	ecs
haproxy	ecs
httpd	ecs
java	ecs
junos	ecs
linux-syslog	ecs
maven	ecs
mcollective	ecs
mongodb	ecs
nagios	ecs
postgresql	ecs
rails	ecs
redis	ecs
ruby	ecs
squid	ecs
zeek	ecs
\.


--
-- Data for Name: fda_logclass; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_logclass (id, created, updated, name, description, contact_person, created_by_id, log_class_status_id, release_id, updated_by_id) FROM stdin;
270fd502-ad78-48fb-ae9d-3066b882f0bf	2023-12-04 08:54:29.178546+00	\N	ExampleClass		logprep@logprep.com	3	f51800f5-d2ca-4c79-888e-bd7ea0186245	1b6f9268-be4d-4422-98c0-edd807f99d5d	\N
\.


--
-- Data for Name: fda_logclassmapping; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_logclassmapping (id, created, updated, created_by_id, log_class_id, updated_by_id, output_keys) FROM stdin;
2236adc1-b737-4544-8f4d-3a2fbb9d7db5	2023-12-04 08:54:29.184932+00	\N	3	270fd502-ad78-48fb-ae9d-3066b882f0bf	\N	{@timestamp,message,meta.provider.name,meta.provider.id,meta.provider,meta,event.time,event.source,event.target,event.systems,event.server,event,provider.name,provider.id,provider,some,grokkedMessage}
\.


--
-- Data for Name: fda_logclassstatus; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_logclassstatus (id, name) FROM stdin;
f51800f5-d2ca-4c79-888e-bd7ea0186245	not_deployed
a3d35690-35cd-4a9a-b75f-a2e2f28efe63	deployed
\.


--
-- Data for Name: fda_logsource; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_logsource (id, created, updated, parameters, created_by_id, log_class_id, updated_by_id) FROM stdin;
\.


--
-- Data for Name: fda_logtarget; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_logtarget (id, required_fields) FROM stdin;
datalake	{@timestamp,tags,client.domain,client.ip,destination.domain,destination.ip,event.code,host.domain,host.hostname,host.ip,log.level,server.domain,server.ip,source.domain,source.ip,user.domain,user.id,user.name}
\.


--
-- Data for Name: fda_mappingfunction; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_mappingfunction (id, created, updated, processor_type, configuration, "position", source_field, created_by_id, logclass_mapping_id, updated_by_id, parent_function_id) FROM stdin;
8efb7596-b41c-48fd-af63-918f6d1a8e1e	2023-12-04 09:06:51.635262+00	\N	dissector	{"generic_rules": [{"filter": "message", "dissector": {"id": "e81c5cc1-224c-4dcf-b7ca-04dc8ac9f8d9", "tests": [], "mapping": {"message": "%{event.time} This is an example message for a request. Source: %{event.source}, Target: %{event.target}. Some more infos: (%{event.systems}) (%{event.server})"}, "regex_fields": [], "tag_on_failure": [], "convert_datatype": {}, "overwrite_target": false, "extend_target_list": false, "delete_source_fields": false}, "description": ""}], "specific_rules": [], "apply_multiple_times": false}	0	message	3	2236adc1-b737-4544-8f4d-3a2fbb9d7db5	\N	\N
d2e5c3f8-831a-4777-aa0e-023daaba7acf	2023-12-04 09:10:45.088802+00	\N	field_manager	{"generic_rules": [{"filter": "meta.provider.name", "description": "", "field_manager": {"id": "9eb21300-497e-4f38-8295-e8513eff81ac", "tests": [], "regex_fields": [], "target_field": "provider.name", "source_fields": ["meta.provider.name"], "tag_on_failure": [], "overwrite_target": false, "extend_target_list": false, "delete_source_fields": false}}], "specific_rules": [], "apply_multiple_times": false}	1	meta.provider.name	3	2236adc1-b737-4544-8f4d-3a2fbb9d7db5	\N	\N
5bfeedeb-4dab-4877-86ca-8563604710e1	2023-12-04 09:11:15.638522+00	\N	field_manager	{"generic_rules": [{"filter": "meta.provider.id", "description": "", "field_manager": {"id": "297c3228-93a2-4934-aeab-1117160f5860", "tests": [], "regex_fields": [], "target_field": "provider.id", "source_fields": ["meta.provider.id"], "tag_on_failure": [], "overwrite_target": false, "extend_target_list": false, "delete_source_fields": false}}], "specific_rules": [], "apply_multiple_times": false}	2	meta.provider.id	3	2236adc1-b737-4544-8f4d-3a2fbb9d7db5	\N	\N
7f6b8156-9c2d-4d89-acdb-7966b1f4fdbe	2024-01-18 14:08:22.247298+00	\N	generic_adder	{"sql_config": null, "generic_rules": [{"filter": "@timestamp", "description": "", "generic_adder": {"id": "1", "add": {"some": "thing"}, "tests": [], "sql_table": {}, "regex_fields": [], "add_from_file": [], "tag_on_failure": [], "overwrite_target": false, "extend_target_list": false, "only_first_existing_file": false}}], "specific_rules": [], "apply_multiple_times": false}	3	@timestamp	3	2236adc1-b737-4544-8f4d-3a2fbb9d7db5	\N	\N
b1430f68-05ad-448d-9827-71cbfd100cec	2024-01-18 14:12:47.890091+00	\N	grokker	{"generic_rules": [{"filter": "message", "grokker": {"id": "safsadasdc24234sdsdf", "tests": [], "mapping": {"message": "%{GREEDYDATA:grokkedMessage}"}, "patterns": {}, "regex_fields": [], "tag_on_failure": [], "convert_datatype": {}, "overwrite_target": false, "extend_target_list": false, "delete_source_fields": false, "ignore_missing_fields": false}, "description": ""}], "specific_rules": [], "custom_patterns_dir": "\\"\\"", "apply_multiple_times": false}	4	message	3	2236adc1-b737-4544-8f4d-3a2fbb9d7db5	\N	\N
\.


--
-- Data for Name: fda_parameterdescription; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_parameterdescription (id, schema, type, required, parameter_name, description) FROM stdin;
ecs.field.name	ecs	field	t	name	Name of the field
ecs.field.level	ecs	field	t	level	ECS Level of maturity of the field (core or extended)
ecs.field.type	ecs	field	t	type	Type of the field. Must be set explicitly, no default
ecs.field.description	ecs	field	t	description	Description of the field
ecs.field.required	ecs	field	f	required	Fields expected in any ECS-compliant event. Currently, only '@timestamp' and 'ecs.version'
ecs.field.short	ecs	field	f	short	Short version of the description to display in small spaces. Short descriptions must not have newlines. Defaults to the main description when absent. If the main description has multiple paragraphs, then a 'short' description with no newlines is required.
ecs.field.example	ecs	field	f	example	A single value example of what can be expected in this field. Example values that are composite types (array, object) should be quoted to avoid YAML interpretation in ECS-generated artifacts and other downstream projects depending on the schema.
ecs.field.ecsMultiFields	ecs	field	f	ecsMultiFields	Specify additional ways to index the field
ecs.field.index	ecs	field	f	index	If 'False', means field is not indexed (overrides type). This parameter has no effect on a 'wildcard' field.
ecs.field.format	ecs	field	f	format	Field format that can be used in a Kibana index template (e.g. String, Bytes, Number).
ecs.field.inputFormat	ecs	field	f	inputFormat	Format of the input (e.g. Nanoseconds).
ecs.field.outputFormat	ecs	field	f	outputFormat	Format of the input (e.g. asMilliseconds).
ecs.field.outputPrecision	ecs	field	f	outputPrecision	Precision of the output.
ecs.field.pattern	ecs	field	f	pattern	A regular expression that expresses the expected constraints of the field's string values.
ecs.field.expectedValues	ecs	field	f	expectedValues	An array of expected values for the field. Schema consumers can validate integrations and mapped data against the listed values. These values are the recommended convention, but users may also use other values.
ecs.field.normalize	ecs	field	f	normalize	Normalization steps that should be applied at ingestion time. The content of the field should be an array (even when there's only one value).
ecs.field.beta	ecs	field	f	beta	Adds a beta marker for the field to the description. The text provided in this attribute is used as content of the beta marker in the documentation. Note that when a whole field set is marked as beta, it is not necessary nor recommended to mark all fields in the field set as beta. Beta notices should not have newlines.
ecs.field.ecsFieldAllowedValues	ecs	field	f	ecsFieldAllowedValues	list of dictionaries with the 'name' and 'description' of the expected values. Optionally, entries in this list can specify 'expected_event_types'. The 'beta' field is also allowed here and will add a beta marker to the allowed value in the ECS categorization docs.
ecs.field.expectedEventTypes	ecs	field	f	expectedEventTypes	list of expected 'event.type' values to use in association with that category.
ecs.field.path	ecs	field	f	path	The full path to the aliases' target field.
ecs.field.scalingFactor	ecs	field	f	scalingFactor	Factor used for scaling.
ecs.field.ignoreAbove	ecs	field	f	ignoreAbove	Strings longer than the ignore above setting will not be indexed or stored.
ecs.fieldset.name	ecs	fieldset	t	name	Name of the field set, lowercased and with underscores to separate words. For programmatic use.
ecs.fieldset.title	ecs	fieldset	t	title	Capitalized name of the field set, with spaces to separate words. For use in documentation section titles.
ecs.fieldset.description	ecs	fieldset	t	description	Description of the field set. Two subsequent newlines create a new paragraph.
ecs.fieldset.fields	ecs	fieldset	t	fields	YAML array as described in the 'List of fields' section below.
ecs.fieldset.short	ecs	fieldset	f	short	Short version of the description to display in small spaces, such as the list of field sets. Short descriptions must not have newlines. Defaults to the main description when absent. If the main description has multiple paragraphs, then a 'short' description with no newlines is required.
ecs.fieldset.root	ecs	fieldset	f	root	Whether or not the fields of this field set should be namespaced under the field set name. Most field sets are expected to have their fields namespaced under the field set name. Only the 'base' field set is expected to set this to true (to define a few root fields like '@timestamp'). Default: false.
ecs.fieldset.group	ecs	fieldset	f	group	To sort field sets against one another. For example the 'base' field set has group=1 and is the first listed in the documentation. All others have group=2 and are therefore after 'base' (sorted alphabetically). Default: 2
ecs.fieldset.type	ecs	fieldset	f	type	at this level, should always be 'group'
ecs.fieldset.reuses	ecs	fieldset	f	reuses	Used to identify which field sets are expected to be reused in multiple places. See 'Field set reuse' for details.
ecs.fieldset.shortOverride	ecs	fieldset	f	shortOverride	Used to override the top-level fieldset's short description when nesting. See 'Field set reuse' for details.
ecs.fieldset.beta	ecs	fieldset	f	beta	Adds a beta marker for the entire fieldset. The text provided in this attribute is used as content of the beta marker in the documentation. Beta notices should not have newlines.
ecs.fieldset.footnote	ecs	fieldset	f	footnote	Additional remarks regarding the fieldset.
\.


--
-- Data for Name: fda_release; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_release (id, created, updated, version_major, version_minor, base_release_id, created_by_id, ecs_version_id, release_status_id, stage_id, updated_by_id) FROM stdin;
09a3ae44-748e-4cfd-b0a6-ed262fe73868	2023-11-21 09:57:30.561503+00	\N	0	0	\N	1	18f6b7af-a59a-4e17-8361-1928341f17a8	721c779c-7ade-43bb-b83e-3117f7fbb8c4	dev	\N
1b6f9268-be4d-4422-98c0-edd807f99d5d	2023-12-04 08:54:12.442495+00	2024-01-19 11:14:19.499309+00	1	0	09a3ae44-748e-4cfd-b0a6-ed262fe73868	3	4aff3b7b-2060-45ad-af71-20ef9e16f6b8	721c779c-7ade-43bb-b83e-3117f7fbb8c4	prod	3
\.


--
-- Data for Name: fda_releasestatus; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_releasestatus (id, name) FROM stdin;
721c779c-7ade-43bb-b83e-3117f7fbb8c4	initial
4047ac31-7c2d-4d9f-a03b-11f3fc2629dd	active
\.


--
-- Data for Name: fda_stage; Type: TABLE DATA; Schema: public; Owner: fda
--

COPY public.fda_stage (name, ordering) FROM stdin;
dev	0
test	1
preprod	2
prod	3
\.


--
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_group_id_seq', 1, false);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_group_permissions_id_seq', 1, false);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_permission_id_seq', 108, true);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_user_groups_id_seq', 1, false);


--
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_user_id_seq', 3, true);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.auth_user_user_permissions_id_seq', 1, false);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.django_admin_log_id_seq', 1, false);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.django_content_type_id_seq', 27, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 34, true);


--
-- Name: fda_ecsmultifield_ecs_fields_id_seq; Type: SEQUENCE SET; Schema: public; Owner: fda
--

SELECT pg_catalog.setval('public.fda_ecsmultifield_ecs_fields_id_seq', 1, false);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: fda_ecsfield fda_ecsfield_name_ecs_fieldset_id_612f4f77_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_name_ecs_fieldset_id_612f4f77_uniq UNIQUE (name, ecs_fieldset_id);


--
-- Name: fda_ecsfield fda_ecsfield_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsfieldallowedvalues fda_ecsfieldallowedvalues_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldallowedvalues
    ADD CONSTRAINT fda_ecsfieldallowedvalues_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsfieldlevel fda_ecsfieldlevel_name_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldlevel
    ADD CONSTRAINT fda_ecsfieldlevel_name_key UNIQUE (name);


--
-- Name: fda_ecsfieldlevel fda_ecsfieldlevel_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldlevel
    ADD CONSTRAINT fda_ecsfieldlevel_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsfieldset fda_ecsfieldset_name_ecs_version_id_08d5d9a4_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldset
    ADD CONSTRAINT fda_ecsfieldset_name_ecs_version_id_08d5d9a4_uniq UNIQUE (name, ecs_version_id);


--
-- Name: fda_ecsfieldset fda_ecsfieldset_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldset
    ADD CONSTRAINT fda_ecsfieldset_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreused_ecs_fieldset_id_ecs_reus_31a640d1_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreused_ecs_fieldset_id_ecs_reus_31a640d1_uniq UNIQUE (ecs_fieldset_id, ecs_reused_at_fieldset_id, reused_as);


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreused_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreused_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsfieldtype fda_ecsfieldtype_name_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldtype
    ADD CONSTRAINT fda_ecsfieldtype_name_key UNIQUE (name);


--
-- Name: fda_ecsfieldtype fda_ecsfieldtype_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldtype
    ADD CONSTRAINT fda_ecsfieldtype_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsmultifield_ecs_fields fda_ecsmultifield_ecs_fi_ecsmultifield_id_ecsfiel_475a6125_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield_ecs_fields
    ADD CONSTRAINT fda_ecsmultifield_ecs_fi_ecsmultifield_id_ecsfiel_475a6125_uniq UNIQUE (ecsmultifield_id, ecsfield_id);


--
-- Name: fda_ecsmultifield_ecs_fields fda_ecsmultifield_ecs_fields_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield_ecs_fields
    ADD CONSTRAINT fda_ecsmultifield_ecs_fields_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsmultifield fda_ecsmultifield_ecs_version_id_name_type_id_fe7bca8e_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_ecs_version_id_name_type_id_fe7bca8e_uniq UNIQUE (ecs_version_id, name, type_id);


--
-- Name: fda_ecsmultifield fda_ecsmultifield_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_pkey PRIMARY KEY (id);


--
-- Name: fda_ecsversion fda_ecsversion_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsversion
    ADD CONSTRAINT fda_ecsversion_pkey PRIMARY KEY (id);


--
-- Name: fda_exampleevent fda_exampleevent_name_log_class_id_e680ae3f_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_name_log_class_id_e680ae3f_uniq UNIQUE (name, log_class_id);


--
-- Name: fda_exampleevent fda_exampleevent_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_pkey PRIMARY KEY (id);


--
-- Name: fda_grokpattern fda_grokpattern_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_grokpattern
    ADD CONSTRAINT fda_grokpattern_pkey PRIMARY KEY (id);


--
-- Name: fda_grokpatterncategory fda_grokpatterncategory_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_grokpatterncategory
    ADD CONSTRAINT fda_grokpatterncategory_pkey PRIMARY KEY (id);


--
-- Name: fda_logclass fda_logclass_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_pkey PRIMARY KEY (id);


--
-- Name: fda_logclass fda_logclass_release_id_name_46797bb3_uniq; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_release_id_name_46797bb3_uniq UNIQUE (release_id, name);


--
-- Name: fda_logclassmapping fda_logclassmapping_log_class_id_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassmapping
    ADD CONSTRAINT fda_logclassmapping_log_class_id_key UNIQUE (log_class_id);


--
-- Name: fda_logclassmapping fda_logclassmapping_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassmapping
    ADD CONSTRAINT fda_logclassmapping_pkey PRIMARY KEY (id);


--
-- Name: fda_logclassstatus fda_logclassstatus_name_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassstatus
    ADD CONSTRAINT fda_logclassstatus_name_key UNIQUE (name);


--
-- Name: fda_logclassstatus fda_logclassstatus_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassstatus
    ADD CONSTRAINT fda_logclassstatus_pkey PRIMARY KEY (id);


--
-- Name: fda_logsource fda_logsource_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logsource
    ADD CONSTRAINT fda_logsource_pkey PRIMARY KEY (id);


--
-- Name: fda_logtarget fda_logtarget_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logtarget
    ADD CONSTRAINT fda_logtarget_pkey PRIMARY KEY (id);


--
-- Name: fda_mappingfunction fda_mappingfunction_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_mappingfunction
    ADD CONSTRAINT fda_mappingfunction_pkey PRIMARY KEY (id);


--
-- Name: fda_parameterdescription fda_parameterdescription_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_parameterdescription
    ADD CONSTRAINT fda_parameterdescription_pkey PRIMARY KEY (id);


--
-- Name: fda_release fda_release_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_pkey PRIMARY KEY (id);


--
-- Name: fda_releasestatus fda_releasestatus_name_key; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_releasestatus
    ADD CONSTRAINT fda_releasestatus_name_key UNIQUE (name);


--
-- Name: fda_releasestatus fda_releasestatus_pkey; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_releasestatus
    ADD CONSTRAINT fda_releasestatus_pkey PRIMARY KEY (id);


--
-- Name: fda_stage fda_stage_name_5c6843a6_pk; Type: CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_stage
    ADD CONSTRAINT fda_stage_name_5c6843a6_pk PRIMARY KEY (name);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: fda_ecsfield_created_by_id_2e022e52; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfield_created_by_id_2e022e52 ON public.fda_ecsfield USING btree (created_by_id);


--
-- Name: fda_ecsfield_ecs_fieldset_id_c3680157; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfield_ecs_fieldset_id_c3680157 ON public.fda_ecsfield USING btree (ecs_fieldset_id);


--
-- Name: fda_ecsfield_level_id_c2106a5d; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfield_level_id_c2106a5d ON public.fda_ecsfield USING btree (level_id);


--
-- Name: fda_ecsfield_type_id_0595e65e; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfield_type_id_0595e65e ON public.fda_ecsfield USING btree (type_id);


--
-- Name: fda_ecsfield_updated_by_id_1384e8f4; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfield_updated_by_id_1384e8f4 ON public.fda_ecsfield USING btree (updated_by_id);


--
-- Name: fda_ecsfieldallowedvalues_created_by_id_a8268dbc; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldallowedvalues_created_by_id_a8268dbc ON public.fda_ecsfieldallowedvalues USING btree (created_by_id);


--
-- Name: fda_ecsfieldallowedvalues_ecs_field_id_802ef220; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldallowedvalues_ecs_field_id_802ef220 ON public.fda_ecsfieldallowedvalues USING btree (ecs_field_id);


--
-- Name: fda_ecsfieldallowedvalues_updated_by_id_9f4f5429; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldallowedvalues_updated_by_id_9f4f5429 ON public.fda_ecsfieldallowedvalues USING btree (updated_by_id);


--
-- Name: fda_ecsfieldlevel_name_e99431dc_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldlevel_name_e99431dc_like ON public.fda_ecsfieldlevel USING btree (name varchar_pattern_ops);


--
-- Name: fda_ecsfieldset_created_by_id_fada43c3; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldset_created_by_id_fada43c3 ON public.fda_ecsfieldset USING btree (created_by_id);


--
-- Name: fda_ecsfieldset_ecs_version_id_a402986e; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldset_ecs_version_id_a402986e ON public.fda_ecsfieldset USING btree (ecs_version_id);


--
-- Name: fda_ecsfieldset_updated_by_id_447168eb; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldset_updated_by_id_447168eb ON public.fda_ecsfieldset USING btree (updated_by_id);


--
-- Name: fda_ecsfieldsetreused_created_by_id_0fe1f9b5; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldsetreused_created_by_id_0fe1f9b5 ON public.fda_ecsfieldsetreused USING btree (created_by_id);


--
-- Name: fda_ecsfieldsetreused_ecs_fieldset_id_df567c8c; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldsetreused_ecs_fieldset_id_df567c8c ON public.fda_ecsfieldsetreused USING btree (ecs_fieldset_id);


--
-- Name: fda_ecsfieldsetreused_ecs_reused_at_fieldset_id_20304c77; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldsetreused_ecs_reused_at_fieldset_id_20304c77 ON public.fda_ecsfieldsetreused USING btree (ecs_reused_at_fieldset_id);


--
-- Name: fda_ecsfieldsetreused_updated_by_id_33d27cf8; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldsetreused_updated_by_id_33d27cf8 ON public.fda_ecsfieldsetreused USING btree (updated_by_id);


--
-- Name: fda_ecsfieldtype_name_11629be2_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsfieldtype_name_11629be2_like ON public.fda_ecsfieldtype USING btree (name varchar_pattern_ops);


--
-- Name: fda_ecsmultifield_created_by_id_c996de7a; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_created_by_id_c996de7a ON public.fda_ecsmultifield USING btree (created_by_id);


--
-- Name: fda_ecsmultifield_ecs_fields_ecsfield_id_8d8af16c; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_ecs_fields_ecsfield_id_8d8af16c ON public.fda_ecsmultifield_ecs_fields USING btree (ecsfield_id);


--
-- Name: fda_ecsmultifield_ecs_fields_ecsmultifield_id_839a37cb; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_ecs_fields_ecsmultifield_id_839a37cb ON public.fda_ecsmultifield_ecs_fields USING btree (ecsmultifield_id);


--
-- Name: fda_ecsmultifield_ecs_version_id_7e8c929e; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_ecs_version_id_7e8c929e ON public.fda_ecsmultifield USING btree (ecs_version_id);


--
-- Name: fda_ecsmultifield_type_id_dfbd0561; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_type_id_dfbd0561 ON public.fda_ecsmultifield USING btree (type_id);


--
-- Name: fda_ecsmultifield_updated_by_id_ef2f0f5a; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsmultifield_updated_by_id_ef2f0f5a ON public.fda_ecsmultifield USING btree (updated_by_id);


--
-- Name: fda_ecsversion_created_by_id_a618328c; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsversion_created_by_id_a618328c ON public.fda_ecsversion USING btree (created_by_id);


--
-- Name: fda_ecsversion_updated_by_id_cf5bd0c6; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_ecsversion_updated_by_id_cf5bd0c6 ON public.fda_ecsversion USING btree (updated_by_id);


--
-- Name: fda_exampleevent_created_by_id_65446562; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_exampleevent_created_by_id_65446562 ON public.fda_exampleevent USING btree (created_by_id);


--
-- Name: fda_exampleevent_log_class_id_ad99b3f5; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_exampleevent_log_class_id_ad99b3f5 ON public.fda_exampleevent USING btree (log_class_id);


--
-- Name: fda_exampleevent_log_source_id_ff9da255; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_exampleevent_log_source_id_ff9da255 ON public.fda_exampleevent USING btree (log_source_id);


--
-- Name: fda_exampleevent_updated_by_id_2a1bc301; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_exampleevent_updated_by_id_2a1bc301 ON public.fda_exampleevent USING btree (updated_by_id);


--
-- Name: fda_grokpattern_category_id_cde2a35d; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_grokpattern_category_id_cde2a35d ON public.fda_grokpattern USING btree (category_id);


--
-- Name: fda_grokpattern_category_id_cde2a35d_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_grokpattern_category_id_cde2a35d_like ON public.fda_grokpattern USING btree (category_id varchar_pattern_ops);


--
-- Name: fda_grokpattern_id_bcc7a391_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_grokpattern_id_bcc7a391_like ON public.fda_grokpattern USING btree (id varchar_pattern_ops);


--
-- Name: fda_grokpatterncategory_id_d33110bc_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_grokpatterncategory_id_d33110bc_like ON public.fda_grokpatterncategory USING btree (id varchar_pattern_ops);


--
-- Name: fda_logclass_created_by_id_e112bbb9; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclass_created_by_id_e112bbb9 ON public.fda_logclass USING btree (created_by_id);


--
-- Name: fda_logclass_log_class_status_id_6d6f777d; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclass_log_class_status_id_6d6f777d ON public.fda_logclass USING btree (log_class_status_id);


--
-- Name: fda_logclass_release_id_616ef330; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclass_release_id_616ef330 ON public.fda_logclass USING btree (release_id);


--
-- Name: fda_logclass_updated_by_id_d068431d; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclass_updated_by_id_d068431d ON public.fda_logclass USING btree (updated_by_id);


--
-- Name: fda_logclassmapping_created_by_id_4d535512; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclassmapping_created_by_id_4d535512 ON public.fda_logclassmapping USING btree (created_by_id);


--
-- Name: fda_logclassmapping_updated_by_id_0db1d396; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclassmapping_updated_by_id_0db1d396 ON public.fda_logclassmapping USING btree (updated_by_id);


--
-- Name: fda_logclassstatus_name_53cbe19d_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logclassstatus_name_53cbe19d_like ON public.fda_logclassstatus USING btree (name varchar_pattern_ops);


--
-- Name: fda_logsource_created_by_id_e916857c; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logsource_created_by_id_e916857c ON public.fda_logsource USING btree (created_by_id);


--
-- Name: fda_logsource_log_class_id_e73bf1d5; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logsource_log_class_id_e73bf1d5 ON public.fda_logsource USING btree (log_class_id);


--
-- Name: fda_logsource_updated_by_id_843edafb; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_logsource_updated_by_id_843edafb ON public.fda_logsource USING btree (updated_by_id);


--
-- Name: fda_mappingfunction_created_by_id_0dd72346; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_mappingfunction_created_by_id_0dd72346 ON public.fda_mappingfunction USING btree (created_by_id);


--
-- Name: fda_mappingfunction_logclass_mapping_id_4a605a0f; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_mappingfunction_logclass_mapping_id_4a605a0f ON public.fda_mappingfunction USING btree (logclass_mapping_id);


--
-- Name: fda_mappingfunction_parent_function_id_6b838c79; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_mappingfunction_parent_function_id_6b838c79 ON public.fda_mappingfunction USING btree (parent_function_id);


--
-- Name: fda_mappingfunction_updated_by_id_fd3a7b53; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_mappingfunction_updated_by_id_fd3a7b53 ON public.fda_mappingfunction USING btree (updated_by_id);


--
-- Name: fda_parameterdescription_id_8bab4540_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_parameterdescription_id_8bab4540_like ON public.fda_parameterdescription USING btree (id varchar_pattern_ops);


--
-- Name: fda_release_base_release_id_acc7d75a; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_base_release_id_acc7d75a ON public.fda_release USING btree (base_release_id);


--
-- Name: fda_release_created_by_id_abd97c27; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_created_by_id_abd97c27 ON public.fda_release USING btree (created_by_id);


--
-- Name: fda_release_ecs_version_id_e8c5c09f; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_ecs_version_id_e8c5c09f ON public.fda_release USING btree (ecs_version_id);


--
-- Name: fda_release_release_status_id_4e6959de; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_release_status_id_4e6959de ON public.fda_release USING btree (release_status_id);


--
-- Name: fda_release_stage_id_ad321a05; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_stage_id_ad321a05 ON public.fda_release USING btree (stage_id);


--
-- Name: fda_release_stage_id_ad321a05_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_stage_id_ad321a05_like ON public.fda_release USING btree (stage_id varchar_pattern_ops);


--
-- Name: fda_release_updated_by_id_1dfb5489; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_release_updated_by_id_1dfb5489 ON public.fda_release USING btree (updated_by_id);


--
-- Name: fda_releasestatus_name_b6b4538e_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_releasestatus_name_b6b4538e_like ON public.fda_releasestatus USING btree (name varchar_pattern_ops);


--
-- Name: fda_stage_name_5c6843a6_like; Type: INDEX; Schema: public; Owner: fda
--

CREATE INDEX fda_stage_name_5c6843a6_like ON public.fda_stage USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfield fda_ecsfield_created_by_id_2e022e52_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_created_by_id_2e022e52_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfield fda_ecsfield_ecs_fieldset_id_c3680157_fk_fda_ecsfieldset_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_ecs_fieldset_id_c3680157_fk_fda_ecsfieldset_id FOREIGN KEY (ecs_fieldset_id) REFERENCES public.fda_ecsfieldset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfield fda_ecsfield_level_id_c2106a5d_fk_fda_ecsfieldlevel_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_level_id_c2106a5d_fk_fda_ecsfieldlevel_id FOREIGN KEY (level_id) REFERENCES public.fda_ecsfieldlevel(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfield fda_ecsfield_type_id_0595e65e_fk_fda_ecsfieldtype_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_type_id_0595e65e_fk_fda_ecsfieldtype_id FOREIGN KEY (type_id) REFERENCES public.fda_ecsfieldtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfield fda_ecsfield_updated_by_id_1384e8f4_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfield
    ADD CONSTRAINT fda_ecsfield_updated_by_id_1384e8f4_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldallowedvalues fda_ecsfieldallowedv_created_by_id_a8268dbc_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldallowedvalues
    ADD CONSTRAINT fda_ecsfieldallowedv_created_by_id_a8268dbc_fk_auth_user FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldallowedvalues fda_ecsfieldallowedv_ecs_field_id_802ef220_fk_fda_ecsfi; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldallowedvalues
    ADD CONSTRAINT fda_ecsfieldallowedv_ecs_field_id_802ef220_fk_fda_ecsfi FOREIGN KEY (ecs_field_id) REFERENCES public.fda_ecsfield(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldallowedvalues fda_ecsfieldallowedv_updated_by_id_9f4f5429_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldallowedvalues
    ADD CONSTRAINT fda_ecsfieldallowedv_updated_by_id_9f4f5429_fk_auth_user FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldset fda_ecsfieldset_created_by_id_fada43c3_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldset
    ADD CONSTRAINT fda_ecsfieldset_created_by_id_fada43c3_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldset fda_ecsfieldset_ecs_version_id_a402986e_fk_fda_ecsversion_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldset
    ADD CONSTRAINT fda_ecsfieldset_ecs_version_id_a402986e_fk_fda_ecsversion_id FOREIGN KEY (ecs_version_id) REFERENCES public.fda_ecsversion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldset fda_ecsfieldset_updated_by_id_447168eb_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldset
    ADD CONSTRAINT fda_ecsfieldset_updated_by_id_447168eb_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreuse_ecs_fieldset_id_df567c8c_fk_fda_ecsfi; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreuse_ecs_fieldset_id_df567c8c_fk_fda_ecsfi FOREIGN KEY (ecs_fieldset_id) REFERENCES public.fda_ecsfieldset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreuse_ecs_reused_at_fields_20304c77_fk_fda_ecsfi; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreuse_ecs_reused_at_fields_20304c77_fk_fda_ecsfi FOREIGN KEY (ecs_reused_at_fieldset_id) REFERENCES public.fda_ecsfieldset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreused_created_by_id_0fe1f9b5_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreused_created_by_id_0fe1f9b5_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsfieldsetreused fda_ecsfieldsetreused_updated_by_id_33d27cf8_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsfieldsetreused
    ADD CONSTRAINT fda_ecsfieldsetreused_updated_by_id_33d27cf8_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield fda_ecsmultifield_created_by_id_c996de7a_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_created_by_id_c996de7a_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield_ecs_fields fda_ecsmultifield_ec_ecsfield_id_8d8af16c_fk_fda_ecsfi; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield_ecs_fields
    ADD CONSTRAINT fda_ecsmultifield_ec_ecsfield_id_8d8af16c_fk_fda_ecsfi FOREIGN KEY (ecsfield_id) REFERENCES public.fda_ecsfield(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield_ecs_fields fda_ecsmultifield_ec_ecsmultifield_id_839a37cb_fk_fda_ecsmu; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield_ecs_fields
    ADD CONSTRAINT fda_ecsmultifield_ec_ecsmultifield_id_839a37cb_fk_fda_ecsmu FOREIGN KEY (ecsmultifield_id) REFERENCES public.fda_ecsmultifield(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield fda_ecsmultifield_ecs_version_id_7e8c929e_fk_fda_ecsversion_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_ecs_version_id_7e8c929e_fk_fda_ecsversion_id FOREIGN KEY (ecs_version_id) REFERENCES public.fda_ecsversion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield fda_ecsmultifield_type_id_dfbd0561_fk_fda_ecsfieldtype_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_type_id_dfbd0561_fk_fda_ecsfieldtype_id FOREIGN KEY (type_id) REFERENCES public.fda_ecsfieldtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsmultifield fda_ecsmultifield_updated_by_id_ef2f0f5a_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsmultifield
    ADD CONSTRAINT fda_ecsmultifield_updated_by_id_ef2f0f5a_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsversion fda_ecsversion_created_by_id_a618328c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsversion
    ADD CONSTRAINT fda_ecsversion_created_by_id_a618328c_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_ecsversion fda_ecsversion_updated_by_id_cf5bd0c6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_ecsversion
    ADD CONSTRAINT fda_ecsversion_updated_by_id_cf5bd0c6_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_exampleevent fda_exampleevent_created_by_id_65446562_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_created_by_id_65446562_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_exampleevent fda_exampleevent_log_class_id_ad99b3f5_fk_fda_logclass_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_log_class_id_ad99b3f5_fk_fda_logclass_id FOREIGN KEY (log_class_id) REFERENCES public.fda_logclass(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_exampleevent fda_exampleevent_log_source_id_ff9da255_fk_fda_logsource_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_log_source_id_ff9da255_fk_fda_logsource_id FOREIGN KEY (log_source_id) REFERENCES public.fda_logsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_exampleevent fda_exampleevent_updated_by_id_2a1bc301_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_exampleevent
    ADD CONSTRAINT fda_exampleevent_updated_by_id_2a1bc301_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_grokpattern fda_grokpattern_category_id_cde2a35d_fk_fda_grokp; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_grokpattern
    ADD CONSTRAINT fda_grokpattern_category_id_cde2a35d_fk_fda_grokp FOREIGN KEY (category_id) REFERENCES public.fda_grokpatterncategory(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclass fda_logclass_created_by_id_e112bbb9_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_created_by_id_e112bbb9_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclass fda_logclass_log_class_status_id_6d6f777d_fk_fda_logcl; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_log_class_status_id_6d6f777d_fk_fda_logcl FOREIGN KEY (log_class_status_id) REFERENCES public.fda_logclassstatus(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclass fda_logclass_release_id_616ef330_fk_fda_release_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_release_id_616ef330_fk_fda_release_id FOREIGN KEY (release_id) REFERENCES public.fda_release(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclass fda_logclass_updated_by_id_d068431d_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclass
    ADD CONSTRAINT fda_logclass_updated_by_id_d068431d_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclassmapping fda_logclassmapping_created_by_id_4d535512_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassmapping
    ADD CONSTRAINT fda_logclassmapping_created_by_id_4d535512_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclassmapping fda_logclassmapping_log_class_id_d8ecd358_fk_fda_logclass_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassmapping
    ADD CONSTRAINT fda_logclassmapping_log_class_id_d8ecd358_fk_fda_logclass_id FOREIGN KEY (log_class_id) REFERENCES public.fda_logclass(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logclassmapping fda_logclassmapping_updated_by_id_0db1d396_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logclassmapping
    ADD CONSTRAINT fda_logclassmapping_updated_by_id_0db1d396_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logsource fda_logsource_created_by_id_e916857c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logsource
    ADD CONSTRAINT fda_logsource_created_by_id_e916857c_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logsource fda_logsource_log_class_id_e73bf1d5_fk_fda_logclass_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logsource
    ADD CONSTRAINT fda_logsource_log_class_id_e73bf1d5_fk_fda_logclass_id FOREIGN KEY (log_class_id) REFERENCES public.fda_logclass(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_logsource fda_logsource_updated_by_id_843edafb_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_logsource
    ADD CONSTRAINT fda_logsource_updated_by_id_843edafb_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_mappingfunction fda_mappingfunction_created_by_id_0dd72346_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_mappingfunction
    ADD CONSTRAINT fda_mappingfunction_created_by_id_0dd72346_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_mappingfunction fda_mappingfunction_logclass_mapping_id_4a605a0f_fk_fda_logcl; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_mappingfunction
    ADD CONSTRAINT fda_mappingfunction_logclass_mapping_id_4a605a0f_fk_fda_logcl FOREIGN KEY (logclass_mapping_id) REFERENCES public.fda_logclassmapping(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_mappingfunction fda_mappingfunction_parent_function_id_6b838c79_fk_fda_mappi; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_mappingfunction
    ADD CONSTRAINT fda_mappingfunction_parent_function_id_6b838c79_fk_fda_mappi FOREIGN KEY (parent_function_id) REFERENCES public.fda_mappingfunction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_mappingfunction fda_mappingfunction_updated_by_id_fd3a7b53_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_mappingfunction
    ADD CONSTRAINT fda_mappingfunction_updated_by_id_fd3a7b53_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_base_release_id_acc7d75a_fk_fda_release_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_base_release_id_acc7d75a_fk_fda_release_id FOREIGN KEY (base_release_id) REFERENCES public.fda_release(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_created_by_id_abd97c27_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_created_by_id_abd97c27_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_ecs_version_id_e8c5c09f_fk_fda_ecsversion_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_ecs_version_id_e8c5c09f_fk_fda_ecsversion_id FOREIGN KEY (ecs_version_id) REFERENCES public.fda_ecsversion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_release_status_id_4e6959de_fk_fda_releasestatus_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_release_status_id_4e6959de_fk_fda_releasestatus_id FOREIGN KEY (release_status_id) REFERENCES public.fda_releasestatus(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_stage_id_ad321a05_fk_fda_stage_name; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_stage_id_ad321a05_fk_fda_stage_name FOREIGN KEY (stage_id) REFERENCES public.fda_stage(name) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fda_release fda_release_updated_by_id_1dfb5489_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: fda
--

ALTER TABLE ONLY public.fda_release
    ADD CONSTRAINT fda_release_updated_by_id_1dfb5489_fk_auth_user_id FOREIGN KEY (updated_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--
