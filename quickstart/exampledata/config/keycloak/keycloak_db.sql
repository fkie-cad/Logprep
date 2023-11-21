--
-- PostgreSQL database dump
--

-- Dumped from database version 16.1
-- Dumped by pg_dump version 16.1

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

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: keycloak
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO keycloak;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_event_entity; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.admin_event_entity (
    id character varying(36) NOT NULL,
    admin_event_time bigint,
    realm_id character varying(255),
    operation_type character varying(255),
    auth_realm_id character varying(255),
    auth_client_id character varying(255),
    auth_user_id character varying(255),
    ip_address character varying(255),
    resource_path character varying(2550),
    representation text,
    error character varying(255),
    resource_type character varying(64)
);


ALTER TABLE public.admin_event_entity OWNER TO keycloak;

--
-- Name: associated_policy; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.associated_policy (
    policy_id character varying(36) NOT NULL,
    associated_policy_id character varying(36) NOT NULL
);


ALTER TABLE public.associated_policy OWNER TO keycloak;

--
-- Name: authentication_execution; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.authentication_execution (
    id character varying(36) NOT NULL,
    alias character varying(255),
    authenticator character varying(36),
    realm_id character varying(36),
    flow_id character varying(36),
    requirement integer,
    priority integer,
    authenticator_flow boolean DEFAULT false NOT NULL,
    auth_flow_id character varying(36),
    auth_config character varying(36)
);


ALTER TABLE public.authentication_execution OWNER TO keycloak;

--
-- Name: authentication_flow; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.authentication_flow (
    id character varying(36) NOT NULL,
    alias character varying(255),
    description character varying(255),
    realm_id character varying(36),
    provider_id character varying(36) DEFAULT 'basic-flow'::character varying NOT NULL,
    top_level boolean DEFAULT false NOT NULL,
    built_in boolean DEFAULT false NOT NULL
);


ALTER TABLE public.authentication_flow OWNER TO keycloak;

--
-- Name: authenticator_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.authenticator_config (
    id character varying(36) NOT NULL,
    alias character varying(255),
    realm_id character varying(36)
);


ALTER TABLE public.authenticator_config OWNER TO keycloak;

--
-- Name: authenticator_config_entry; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.authenticator_config_entry (
    authenticator_id character varying(36) NOT NULL,
    value text,
    name character varying(255) NOT NULL
);


ALTER TABLE public.authenticator_config_entry OWNER TO keycloak;

--
-- Name: broker_link; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.broker_link (
    identity_provider character varying(255) NOT NULL,
    storage_provider_id character varying(255),
    realm_id character varying(36) NOT NULL,
    broker_user_id character varying(255),
    broker_username character varying(255),
    token text,
    user_id character varying(255) NOT NULL
);


ALTER TABLE public.broker_link OWNER TO keycloak;

--
-- Name: client; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client (
    id character varying(36) NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    full_scope_allowed boolean DEFAULT false NOT NULL,
    client_id character varying(255),
    not_before integer,
    public_client boolean DEFAULT false NOT NULL,
    secret character varying(255),
    base_url character varying(255),
    bearer_only boolean DEFAULT false NOT NULL,
    management_url character varying(255),
    surrogate_auth_required boolean DEFAULT false NOT NULL,
    realm_id character varying(36),
    protocol character varying(255),
    node_rereg_timeout integer DEFAULT 0,
    frontchannel_logout boolean DEFAULT false NOT NULL,
    consent_required boolean DEFAULT false NOT NULL,
    name character varying(255),
    service_accounts_enabled boolean DEFAULT false NOT NULL,
    client_authenticator_type character varying(255),
    root_url character varying(255),
    description character varying(255),
    registration_token character varying(255),
    standard_flow_enabled boolean DEFAULT true NOT NULL,
    implicit_flow_enabled boolean DEFAULT false NOT NULL,
    direct_access_grants_enabled boolean DEFAULT false NOT NULL,
    always_display_in_console boolean DEFAULT false NOT NULL
);


ALTER TABLE public.client OWNER TO keycloak;

--
-- Name: client_attributes; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_attributes (
    client_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    value text
);


ALTER TABLE public.client_attributes OWNER TO keycloak;

--
-- Name: client_auth_flow_bindings; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_auth_flow_bindings (
    client_id character varying(36) NOT NULL,
    flow_id character varying(36),
    binding_name character varying(255) NOT NULL
);


ALTER TABLE public.client_auth_flow_bindings OWNER TO keycloak;

--
-- Name: client_initial_access; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_initial_access (
    id character varying(36) NOT NULL,
    realm_id character varying(36) NOT NULL,
    "timestamp" integer,
    expiration integer,
    count integer,
    remaining_count integer
);


ALTER TABLE public.client_initial_access OWNER TO keycloak;

--
-- Name: client_node_registrations; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_node_registrations (
    client_id character varying(36) NOT NULL,
    value integer,
    name character varying(255) NOT NULL
);


ALTER TABLE public.client_node_registrations OWNER TO keycloak;

--
-- Name: client_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_scope (
    id character varying(36) NOT NULL,
    name character varying(255),
    realm_id character varying(36),
    description character varying(255),
    protocol character varying(255)
);


ALTER TABLE public.client_scope OWNER TO keycloak;

--
-- Name: client_scope_attributes; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_scope_attributes (
    scope_id character varying(36) NOT NULL,
    value character varying(2048),
    name character varying(255) NOT NULL
);


ALTER TABLE public.client_scope_attributes OWNER TO keycloak;

--
-- Name: client_scope_client; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_scope_client (
    client_id character varying(255) NOT NULL,
    scope_id character varying(255) NOT NULL,
    default_scope boolean DEFAULT false NOT NULL
);


ALTER TABLE public.client_scope_client OWNER TO keycloak;

--
-- Name: client_scope_role_mapping; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_scope_role_mapping (
    scope_id character varying(36) NOT NULL,
    role_id character varying(36) NOT NULL
);


ALTER TABLE public.client_scope_role_mapping OWNER TO keycloak;

--
-- Name: client_session; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_session (
    id character varying(36) NOT NULL,
    client_id character varying(36),
    redirect_uri character varying(255),
    state character varying(255),
    "timestamp" integer,
    session_id character varying(36),
    auth_method character varying(255),
    realm_id character varying(255),
    auth_user_id character varying(36),
    current_action character varying(36)
);


ALTER TABLE public.client_session OWNER TO keycloak;

--
-- Name: client_session_auth_status; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_session_auth_status (
    authenticator character varying(36) NOT NULL,
    status integer,
    client_session character varying(36) NOT NULL
);


ALTER TABLE public.client_session_auth_status OWNER TO keycloak;

--
-- Name: client_session_note; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_session_note (
    name character varying(255) NOT NULL,
    value character varying(255),
    client_session character varying(36) NOT NULL
);


ALTER TABLE public.client_session_note OWNER TO keycloak;

--
-- Name: client_session_prot_mapper; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_session_prot_mapper (
    protocol_mapper_id character varying(36) NOT NULL,
    client_session character varying(36) NOT NULL
);


ALTER TABLE public.client_session_prot_mapper OWNER TO keycloak;

--
-- Name: client_session_role; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_session_role (
    role_id character varying(255) NOT NULL,
    client_session character varying(36) NOT NULL
);


ALTER TABLE public.client_session_role OWNER TO keycloak;

--
-- Name: client_user_session_note; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.client_user_session_note (
    name character varying(255) NOT NULL,
    value character varying(2048),
    client_session character varying(36) NOT NULL
);


ALTER TABLE public.client_user_session_note OWNER TO keycloak;

--
-- Name: component; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.component (
    id character varying(36) NOT NULL,
    name character varying(255),
    parent_id character varying(36),
    provider_id character varying(36),
    provider_type character varying(255),
    realm_id character varying(36),
    sub_type character varying(255)
);


ALTER TABLE public.component OWNER TO keycloak;

--
-- Name: component_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.component_config (
    id character varying(36) NOT NULL,
    component_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    value character varying(4000)
);


ALTER TABLE public.component_config OWNER TO keycloak;

--
-- Name: composite_role; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.composite_role (
    composite character varying(36) NOT NULL,
    child_role character varying(36) NOT NULL
);


ALTER TABLE public.composite_role OWNER TO keycloak;

--
-- Name: credential; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.credential (
    id character varying(36) NOT NULL,
    salt bytea,
    type character varying(255),
    user_id character varying(36),
    created_date bigint,
    user_label character varying(255),
    secret_data text,
    credential_data text,
    priority integer
);


ALTER TABLE public.credential OWNER TO keycloak;

--
-- Name: databasechangelog; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.databasechangelog (
    id character varying(255) NOT NULL,
    author character varying(255) NOT NULL,
    filename character varying(255) NOT NULL,
    dateexecuted timestamp without time zone NOT NULL,
    orderexecuted integer NOT NULL,
    exectype character varying(10) NOT NULL,
    md5sum character varying(35),
    description character varying(255),
    comments character varying(255),
    tag character varying(255),
    liquibase character varying(20),
    contexts character varying(255),
    labels character varying(255),
    deployment_id character varying(10)
);


ALTER TABLE public.databasechangelog OWNER TO keycloak;

--
-- Name: databasechangeloglock; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.databasechangeloglock (
    id integer NOT NULL,
    locked boolean NOT NULL,
    lockgranted timestamp without time zone,
    lockedby character varying(255)
);


ALTER TABLE public.databasechangeloglock OWNER TO keycloak;

--
-- Name: default_client_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.default_client_scope (
    realm_id character varying(36) NOT NULL,
    scope_id character varying(36) NOT NULL,
    default_scope boolean DEFAULT false NOT NULL
);


ALTER TABLE public.default_client_scope OWNER TO keycloak;

--
-- Name: event_entity; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.event_entity (
    id character varying(36) NOT NULL,
    client_id character varying(255),
    details_json character varying(2550),
    error character varying(255),
    ip_address character varying(255),
    realm_id character varying(255),
    session_id character varying(255),
    event_time bigint,
    type character varying(255),
    user_id character varying(255)
);


ALTER TABLE public.event_entity OWNER TO keycloak;

--
-- Name: fed_user_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_attribute (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36),
    value character varying(2024)
);


ALTER TABLE public.fed_user_attribute OWNER TO keycloak;

--
-- Name: fed_user_consent; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_consent (
    id character varying(36) NOT NULL,
    client_id character varying(255),
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36),
    created_date bigint,
    last_updated_date bigint,
    client_storage_provider character varying(36),
    external_client_id character varying(255)
);


ALTER TABLE public.fed_user_consent OWNER TO keycloak;

--
-- Name: fed_user_consent_cl_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_consent_cl_scope (
    user_consent_id character varying(36) NOT NULL,
    scope_id character varying(36) NOT NULL
);


ALTER TABLE public.fed_user_consent_cl_scope OWNER TO keycloak;

--
-- Name: fed_user_credential; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_credential (
    id character varying(36) NOT NULL,
    salt bytea,
    type character varying(255),
    created_date bigint,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36),
    user_label character varying(255),
    secret_data text,
    credential_data text,
    priority integer
);


ALTER TABLE public.fed_user_credential OWNER TO keycloak;

--
-- Name: fed_user_group_membership; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_group_membership (
    group_id character varying(36) NOT NULL,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36)
);


ALTER TABLE public.fed_user_group_membership OWNER TO keycloak;

--
-- Name: fed_user_required_action; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_required_action (
    required_action character varying(255) DEFAULT ' '::character varying NOT NULL,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36)
);


ALTER TABLE public.fed_user_required_action OWNER TO keycloak;

--
-- Name: fed_user_role_mapping; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.fed_user_role_mapping (
    role_id character varying(36) NOT NULL,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    storage_provider_id character varying(36)
);


ALTER TABLE public.fed_user_role_mapping OWNER TO keycloak;

--
-- Name: federated_identity; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.federated_identity (
    identity_provider character varying(255) NOT NULL,
    realm_id character varying(36),
    federated_user_id character varying(255),
    federated_username character varying(255),
    token text,
    user_id character varying(36) NOT NULL
);


ALTER TABLE public.federated_identity OWNER TO keycloak;

--
-- Name: federated_user; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.federated_user (
    id character varying(255) NOT NULL,
    storage_provider_id character varying(255),
    realm_id character varying(36) NOT NULL
);


ALTER TABLE public.federated_user OWNER TO keycloak;

--
-- Name: group_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.group_attribute (
    id character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL,
    name character varying(255) NOT NULL,
    value character varying(255),
    group_id character varying(36) NOT NULL
);


ALTER TABLE public.group_attribute OWNER TO keycloak;

--
-- Name: group_role_mapping; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.group_role_mapping (
    role_id character varying(36) NOT NULL,
    group_id character varying(36) NOT NULL
);


ALTER TABLE public.group_role_mapping OWNER TO keycloak;

--
-- Name: identity_provider; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.identity_provider (
    internal_id character varying(36) NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    provider_alias character varying(255),
    provider_id character varying(255),
    store_token boolean DEFAULT false NOT NULL,
    authenticate_by_default boolean DEFAULT false NOT NULL,
    realm_id character varying(36),
    add_token_role boolean DEFAULT true NOT NULL,
    trust_email boolean DEFAULT false NOT NULL,
    first_broker_login_flow_id character varying(36),
    post_broker_login_flow_id character varying(36),
    provider_display_name character varying(255),
    link_only boolean DEFAULT false NOT NULL
);


ALTER TABLE public.identity_provider OWNER TO keycloak;

--
-- Name: identity_provider_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.identity_provider_config (
    identity_provider_id character varying(36) NOT NULL,
    value text,
    name character varying(255) NOT NULL
);


ALTER TABLE public.identity_provider_config OWNER TO keycloak;

--
-- Name: identity_provider_mapper; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.identity_provider_mapper (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    idp_alias character varying(255) NOT NULL,
    idp_mapper_name character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL
);


ALTER TABLE public.identity_provider_mapper OWNER TO keycloak;

--
-- Name: idp_mapper_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.idp_mapper_config (
    idp_mapper_id character varying(36) NOT NULL,
    value text,
    name character varying(255) NOT NULL
);


ALTER TABLE public.idp_mapper_config OWNER TO keycloak;

--
-- Name: keycloak_group; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.keycloak_group (
    id character varying(36) NOT NULL,
    name character varying(255),
    parent_group character varying(36) NOT NULL,
    realm_id character varying(36)
);


ALTER TABLE public.keycloak_group OWNER TO keycloak;

--
-- Name: keycloak_role; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.keycloak_role (
    id character varying(36) NOT NULL,
    client_realm_constraint character varying(255),
    client_role boolean DEFAULT false NOT NULL,
    description character varying(255),
    name character varying(255),
    realm_id character varying(255),
    client character varying(36),
    realm character varying(36)
);


ALTER TABLE public.keycloak_role OWNER TO keycloak;

--
-- Name: migration_model; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.migration_model (
    id character varying(36) NOT NULL,
    version character varying(36),
    update_time bigint DEFAULT 0 NOT NULL
);


ALTER TABLE public.migration_model OWNER TO keycloak;

--
-- Name: offline_client_session; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.offline_client_session (
    user_session_id character varying(36) NOT NULL,
    client_id character varying(255) NOT NULL,
    offline_flag character varying(4) NOT NULL,
    "timestamp" integer,
    data text,
    client_storage_provider character varying(36) DEFAULT 'local'::character varying NOT NULL,
    external_client_id character varying(255) DEFAULT 'local'::character varying NOT NULL
);


ALTER TABLE public.offline_client_session OWNER TO keycloak;

--
-- Name: offline_user_session; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.offline_user_session (
    user_session_id character varying(36) NOT NULL,
    user_id character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    created_on integer NOT NULL,
    offline_flag character varying(4) NOT NULL,
    data text,
    last_session_refresh integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.offline_user_session OWNER TO keycloak;

--
-- Name: policy_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.policy_config (
    policy_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    value text
);


ALTER TABLE public.policy_config OWNER TO keycloak;

--
-- Name: protocol_mapper; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.protocol_mapper (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    protocol character varying(255) NOT NULL,
    protocol_mapper_name character varying(255) NOT NULL,
    client_id character varying(36),
    client_scope_id character varying(36)
);


ALTER TABLE public.protocol_mapper OWNER TO keycloak;

--
-- Name: protocol_mapper_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.protocol_mapper_config (
    protocol_mapper_id character varying(36) NOT NULL,
    value text,
    name character varying(255) NOT NULL
);


ALTER TABLE public.protocol_mapper_config OWNER TO keycloak;

--
-- Name: realm; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm (
    id character varying(36) NOT NULL,
    access_code_lifespan integer,
    user_action_lifespan integer,
    access_token_lifespan integer,
    account_theme character varying(255),
    admin_theme character varying(255),
    email_theme character varying(255),
    enabled boolean DEFAULT false NOT NULL,
    events_enabled boolean DEFAULT false NOT NULL,
    events_expiration bigint,
    login_theme character varying(255),
    name character varying(255),
    not_before integer,
    password_policy character varying(2550),
    registration_allowed boolean DEFAULT false NOT NULL,
    remember_me boolean DEFAULT false NOT NULL,
    reset_password_allowed boolean DEFAULT false NOT NULL,
    social boolean DEFAULT false NOT NULL,
    ssl_required character varying(255),
    sso_idle_timeout integer,
    sso_max_lifespan integer,
    update_profile_on_soc_login boolean DEFAULT false NOT NULL,
    verify_email boolean DEFAULT false NOT NULL,
    master_admin_client character varying(36),
    login_lifespan integer,
    internationalization_enabled boolean DEFAULT false NOT NULL,
    default_locale character varying(255),
    reg_email_as_username boolean DEFAULT false NOT NULL,
    admin_events_enabled boolean DEFAULT false NOT NULL,
    admin_events_details_enabled boolean DEFAULT false NOT NULL,
    edit_username_allowed boolean DEFAULT false NOT NULL,
    otp_policy_counter integer DEFAULT 0,
    otp_policy_window integer DEFAULT 1,
    otp_policy_period integer DEFAULT 30,
    otp_policy_digits integer DEFAULT 6,
    otp_policy_alg character varying(36) DEFAULT 'HmacSHA1'::character varying,
    otp_policy_type character varying(36) DEFAULT 'totp'::character varying,
    browser_flow character varying(36),
    registration_flow character varying(36),
    direct_grant_flow character varying(36),
    reset_credentials_flow character varying(36),
    client_auth_flow character varying(36),
    offline_session_idle_timeout integer DEFAULT 0,
    revoke_refresh_token boolean DEFAULT false NOT NULL,
    access_token_life_implicit integer DEFAULT 0,
    login_with_email_allowed boolean DEFAULT true NOT NULL,
    duplicate_emails_allowed boolean DEFAULT false NOT NULL,
    docker_auth_flow character varying(36),
    refresh_token_max_reuse integer DEFAULT 0,
    allow_user_managed_access boolean DEFAULT false NOT NULL,
    sso_max_lifespan_remember_me integer DEFAULT 0 NOT NULL,
    sso_idle_timeout_remember_me integer DEFAULT 0 NOT NULL,
    default_role character varying(255)
);


ALTER TABLE public.realm OWNER TO keycloak;

--
-- Name: realm_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_attribute (
    name character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL,
    value text
);


ALTER TABLE public.realm_attribute OWNER TO keycloak;

--
-- Name: realm_default_groups; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_default_groups (
    realm_id character varying(36) NOT NULL,
    group_id character varying(36) NOT NULL
);


ALTER TABLE public.realm_default_groups OWNER TO keycloak;

--
-- Name: realm_enabled_event_types; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_enabled_event_types (
    realm_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.realm_enabled_event_types OWNER TO keycloak;

--
-- Name: realm_events_listeners; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_events_listeners (
    realm_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.realm_events_listeners OWNER TO keycloak;

--
-- Name: realm_localizations; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_localizations (
    realm_id character varying(255) NOT NULL,
    locale character varying(255) NOT NULL,
    texts text NOT NULL
);


ALTER TABLE public.realm_localizations OWNER TO keycloak;

--
-- Name: realm_required_credential; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_required_credential (
    type character varying(255) NOT NULL,
    form_label character varying(255),
    input boolean DEFAULT false NOT NULL,
    secret boolean DEFAULT false NOT NULL,
    realm_id character varying(36) NOT NULL
);


ALTER TABLE public.realm_required_credential OWNER TO keycloak;

--
-- Name: realm_smtp_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_smtp_config (
    realm_id character varying(36) NOT NULL,
    value character varying(255),
    name character varying(255) NOT NULL
);


ALTER TABLE public.realm_smtp_config OWNER TO keycloak;

--
-- Name: realm_supported_locales; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.realm_supported_locales (
    realm_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.realm_supported_locales OWNER TO keycloak;

--
-- Name: redirect_uris; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.redirect_uris (
    client_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.redirect_uris OWNER TO keycloak;

--
-- Name: required_action_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.required_action_config (
    required_action_id character varying(36) NOT NULL,
    value text,
    name character varying(255) NOT NULL
);


ALTER TABLE public.required_action_config OWNER TO keycloak;

--
-- Name: required_action_provider; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.required_action_provider (
    id character varying(36) NOT NULL,
    alias character varying(255),
    name character varying(255),
    realm_id character varying(36),
    enabled boolean DEFAULT false NOT NULL,
    default_action boolean DEFAULT false NOT NULL,
    provider_id character varying(255),
    priority integer
);


ALTER TABLE public.required_action_provider OWNER TO keycloak;

--
-- Name: resource_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_attribute (
    id character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL,
    name character varying(255) NOT NULL,
    value character varying(255),
    resource_id character varying(36) NOT NULL
);


ALTER TABLE public.resource_attribute OWNER TO keycloak;

--
-- Name: resource_policy; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_policy (
    resource_id character varying(36) NOT NULL,
    policy_id character varying(36) NOT NULL
);


ALTER TABLE public.resource_policy OWNER TO keycloak;

--
-- Name: resource_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_scope (
    resource_id character varying(36) NOT NULL,
    scope_id character varying(36) NOT NULL
);


ALTER TABLE public.resource_scope OWNER TO keycloak;

--
-- Name: resource_server; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_server (
    id character varying(36) NOT NULL,
    allow_rs_remote_mgmt boolean DEFAULT false NOT NULL,
    policy_enforce_mode smallint NOT NULL,
    decision_strategy smallint DEFAULT 1 NOT NULL
);


ALTER TABLE public.resource_server OWNER TO keycloak;

--
-- Name: resource_server_perm_ticket; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_server_perm_ticket (
    id character varying(36) NOT NULL,
    owner character varying(255) NOT NULL,
    requester character varying(255) NOT NULL,
    created_timestamp bigint NOT NULL,
    granted_timestamp bigint,
    resource_id character varying(36) NOT NULL,
    scope_id character varying(36),
    resource_server_id character varying(36) NOT NULL,
    policy_id character varying(36)
);


ALTER TABLE public.resource_server_perm_ticket OWNER TO keycloak;

--
-- Name: resource_server_policy; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_server_policy (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(255),
    type character varying(255) NOT NULL,
    decision_strategy smallint,
    logic smallint,
    resource_server_id character varying(36) NOT NULL,
    owner character varying(255)
);


ALTER TABLE public.resource_server_policy OWNER TO keycloak;

--
-- Name: resource_server_resource; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_server_resource (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(255),
    icon_uri character varying(255),
    owner character varying(255) NOT NULL,
    resource_server_id character varying(36) NOT NULL,
    owner_managed_access boolean DEFAULT false NOT NULL,
    display_name character varying(255)
);


ALTER TABLE public.resource_server_resource OWNER TO keycloak;

--
-- Name: resource_server_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_server_scope (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    icon_uri character varying(255),
    resource_server_id character varying(36) NOT NULL,
    display_name character varying(255)
);


ALTER TABLE public.resource_server_scope OWNER TO keycloak;

--
-- Name: resource_uris; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.resource_uris (
    resource_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.resource_uris OWNER TO keycloak;

--
-- Name: role_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.role_attribute (
    id character varying(36) NOT NULL,
    role_id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    value character varying(255)
);


ALTER TABLE public.role_attribute OWNER TO keycloak;

--
-- Name: scope_mapping; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.scope_mapping (
    client_id character varying(36) NOT NULL,
    role_id character varying(36) NOT NULL
);


ALTER TABLE public.scope_mapping OWNER TO keycloak;

--
-- Name: scope_policy; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.scope_policy (
    scope_id character varying(36) NOT NULL,
    policy_id character varying(36) NOT NULL
);


ALTER TABLE public.scope_policy OWNER TO keycloak;

--
-- Name: user_attribute; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_attribute (
    name character varying(255) NOT NULL,
    value character varying(255),
    user_id character varying(36) NOT NULL,
    id character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL
);


ALTER TABLE public.user_attribute OWNER TO keycloak;

--
-- Name: user_consent; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_consent (
    id character varying(36) NOT NULL,
    client_id character varying(255),
    user_id character varying(36) NOT NULL,
    created_date bigint,
    last_updated_date bigint,
    client_storage_provider character varying(36),
    external_client_id character varying(255)
);


ALTER TABLE public.user_consent OWNER TO keycloak;

--
-- Name: user_consent_client_scope; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_consent_client_scope (
    user_consent_id character varying(36) NOT NULL,
    scope_id character varying(36) NOT NULL
);


ALTER TABLE public.user_consent_client_scope OWNER TO keycloak;

--
-- Name: user_entity; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_entity (
    id character varying(36) NOT NULL,
    email character varying(255),
    email_constraint character varying(255),
    email_verified boolean DEFAULT false NOT NULL,
    enabled boolean DEFAULT false NOT NULL,
    federation_link character varying(255),
    first_name character varying(255),
    last_name character varying(255),
    realm_id character varying(255),
    username character varying(255),
    created_timestamp bigint,
    service_account_client_link character varying(255),
    not_before integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.user_entity OWNER TO keycloak;

--
-- Name: user_federation_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_federation_config (
    user_federation_provider_id character varying(36) NOT NULL,
    value character varying(255),
    name character varying(255) NOT NULL
);


ALTER TABLE public.user_federation_config OWNER TO keycloak;

--
-- Name: user_federation_mapper; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_federation_mapper (
    id character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    federation_provider_id character varying(36) NOT NULL,
    federation_mapper_type character varying(255) NOT NULL,
    realm_id character varying(36) NOT NULL
);


ALTER TABLE public.user_federation_mapper OWNER TO keycloak;

--
-- Name: user_federation_mapper_config; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_federation_mapper_config (
    user_federation_mapper_id character varying(36) NOT NULL,
    value character varying(255),
    name character varying(255) NOT NULL
);


ALTER TABLE public.user_federation_mapper_config OWNER TO keycloak;

--
-- Name: user_federation_provider; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_federation_provider (
    id character varying(36) NOT NULL,
    changed_sync_period integer,
    display_name character varying(255),
    full_sync_period integer,
    last_sync integer,
    priority integer,
    provider_name character varying(255),
    realm_id character varying(36)
);


ALTER TABLE public.user_federation_provider OWNER TO keycloak;

--
-- Name: user_group_membership; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_group_membership (
    group_id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL
);


ALTER TABLE public.user_group_membership OWNER TO keycloak;

--
-- Name: user_required_action; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_required_action (
    user_id character varying(36) NOT NULL,
    required_action character varying(255) DEFAULT ' '::character varying NOT NULL
);


ALTER TABLE public.user_required_action OWNER TO keycloak;

--
-- Name: user_role_mapping; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_role_mapping (
    role_id character varying(255) NOT NULL,
    user_id character varying(36) NOT NULL
);


ALTER TABLE public.user_role_mapping OWNER TO keycloak;

--
-- Name: user_session; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_session (
    id character varying(36) NOT NULL,
    auth_method character varying(255),
    ip_address character varying(255),
    last_session_refresh integer,
    login_username character varying(255),
    realm_id character varying(255),
    remember_me boolean DEFAULT false NOT NULL,
    started integer,
    user_id character varying(255),
    user_session_state integer,
    broker_session_id character varying(255),
    broker_user_id character varying(255)
);


ALTER TABLE public.user_session OWNER TO keycloak;

--
-- Name: user_session_note; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.user_session_note (
    user_session character varying(36) NOT NULL,
    name character varying(255) NOT NULL,
    value character varying(2048)
);


ALTER TABLE public.user_session_note OWNER TO keycloak;

--
-- Name: username_login_failure; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.username_login_failure (
    realm_id character varying(36) NOT NULL,
    username character varying(255) NOT NULL,
    failed_login_not_before integer,
    last_failure bigint,
    last_ip_failure character varying(255),
    num_failures integer
);


ALTER TABLE public.username_login_failure OWNER TO keycloak;

--
-- Name: web_origins; Type: TABLE; Schema: public; Owner: keycloak
--

CREATE TABLE public.web_origins (
    client_id character varying(36) NOT NULL,
    value character varying(255) NOT NULL
);


ALTER TABLE public.web_origins OWNER TO keycloak;

--
-- Data for Name: admin_event_entity; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.admin_event_entity (id, admin_event_time, realm_id, operation_type, auth_realm_id, auth_client_id, auth_user_id, ip_address, resource_path, representation, error, resource_type) FROM stdin;
\.


--
-- Data for Name: associated_policy; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.associated_policy (policy_id, associated_policy_id) FROM stdin;
\.


--
-- Data for Name: authentication_execution; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.authentication_execution (id, alias, authenticator, realm_id, flow_id, requirement, priority, authenticator_flow, auth_flow_id, auth_config) FROM stdin;
698646fc-57dc-4bef-8cde-eed423a8b028	\N	auth-cookie	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	261ee39e-ad77-4d9d-8e56-15ec77ea611b	2	10	f	\N	\N
725159ea-38db-42f1-92c5-d5c7599e079d	\N	auth-spnego	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	261ee39e-ad77-4d9d-8e56-15ec77ea611b	3	20	f	\N	\N
c9ba1342-a350-43d9-b167-0f9415127010	\N	identity-provider-redirector	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	261ee39e-ad77-4d9d-8e56-15ec77ea611b	2	25	f	\N	\N
f2ed0b57-9d53-49a2-96d3-0f94ee66f3b4	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	261ee39e-ad77-4d9d-8e56-15ec77ea611b	2	30	t	f3dbb7c6-92ab-4824-9081-43d2c475a949	\N
07fedc89-de62-475a-92ee-6675c14a5e14	\N	auth-username-password-form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f3dbb7c6-92ab-4824-9081-43d2c475a949	0	10	f	\N	\N
13e50efa-dbce-4930-9d1a-9f6618441c6d	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f3dbb7c6-92ab-4824-9081-43d2c475a949	1	20	t	b16e2cfc-d6d9-4b17-b58f-482dd04b7474	\N
60e1e76c-1364-4264-888a-1e8f43d4ea0f	\N	conditional-user-configured	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b16e2cfc-d6d9-4b17-b58f-482dd04b7474	0	10	f	\N	\N
b27ea728-baec-4b59-a79b-c7441580446d	\N	auth-otp-form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b16e2cfc-d6d9-4b17-b58f-482dd04b7474	0	20	f	\N	\N
9a457d86-7a9d-4e85-8616-edc9c1f0435a	\N	direct-grant-validate-username	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b31ebba6-89c4-4d34-bd26-18f958560753	0	10	f	\N	\N
f839f182-5c5d-417c-9e85-8c9098fb319b	\N	direct-grant-validate-password	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b31ebba6-89c4-4d34-bd26-18f958560753	0	20	f	\N	\N
2632109e-a8b6-4f59-81d5-4b49082c0cee	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b31ebba6-89c4-4d34-bd26-18f958560753	1	30	t	a031f3e8-d5fd-4677-937e-884c23b9d7f9	\N
a85219be-190c-4c3a-8e32-b53912477368	\N	conditional-user-configured	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	a031f3e8-d5fd-4677-937e-884c23b9d7f9	0	10	f	\N	\N
57a149a8-a13e-41fc-b02d-2b44dc33cdc4	\N	direct-grant-validate-otp	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	a031f3e8-d5fd-4677-937e-884c23b9d7f9	0	20	f	\N	\N
b45958f9-952e-4285-95f6-4dd7d0e730ce	\N	registration-page-form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	071c0a54-e2e9-4791-bb7e-72853915e371	0	10	t	7700368f-d112-477a-aeb4-675f0bafff41	\N
0262d79c-8376-4d21-9ede-008a72beec4f	\N	registration-user-creation	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7700368f-d112-477a-aeb4-675f0bafff41	0	20	f	\N	\N
f2ddf665-9fac-47c9-9031-a5973cebff4f	\N	registration-profile-action	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7700368f-d112-477a-aeb4-675f0bafff41	0	40	f	\N	\N
eedf36e2-fbaa-4ba6-ba66-ec6392e50c4a	\N	registration-password-action	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7700368f-d112-477a-aeb4-675f0bafff41	0	50	f	\N	\N
aa15a066-fd21-4523-b695-543d40263a15	\N	registration-recaptcha-action	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7700368f-d112-477a-aeb4-675f0bafff41	3	60	f	\N	\N
55bed7d8-dee6-4f7f-8054-aa8935f7a537	\N	registration-terms-and-conditions	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7700368f-d112-477a-aeb4-675f0bafff41	3	70	f	\N	\N
c1c5e423-8658-4249-9766-ee0e5e989b1b	\N	reset-credentials-choose-user	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0b110242-a5a9-40bd-8ac7-78fec175f3b8	0	10	f	\N	\N
0fa27b56-69b2-4228-8cdd-5226ab6d97e3	\N	reset-credential-email	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0b110242-a5a9-40bd-8ac7-78fec175f3b8	0	20	f	\N	\N
2aca3a81-d082-421e-ad12-b8b64e4de425	\N	reset-password	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0b110242-a5a9-40bd-8ac7-78fec175f3b8	0	30	f	\N	\N
b6e344d5-3586-46b0-8f27-29ab9a566e45	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0b110242-a5a9-40bd-8ac7-78fec175f3b8	1	40	t	82800697-006e-458e-881d-9bef7a683964	\N
a4721b45-e5e5-4d59-80c1-3ec74f918d92	\N	conditional-user-configured	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	82800697-006e-458e-881d-9bef7a683964	0	10	f	\N	\N
57adbefe-d071-422d-8471-890a276e523e	\N	reset-otp	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	82800697-006e-458e-881d-9bef7a683964	0	20	f	\N	\N
b33c517c-46be-4ccc-b753-af280d4be3ce	\N	client-secret	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	ecb294d1-bb2c-458b-96e6-257a74ee42de	2	10	f	\N	\N
7acb28cd-6489-4486-8ae6-c2dbd8eb6209	\N	client-jwt	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	ecb294d1-bb2c-458b-96e6-257a74ee42de	2	20	f	\N	\N
6d1b4ed6-fd4f-45aa-ad1b-b335ea55e66f	\N	client-secret-jwt	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	ecb294d1-bb2c-458b-96e6-257a74ee42de	2	30	f	\N	\N
eacddbe5-025c-44f5-b111-22b8a3726557	\N	client-x509	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	ecb294d1-bb2c-458b-96e6-257a74ee42de	2	40	f	\N	\N
764a0362-11c1-46b8-8cb2-da68e050c9ed	\N	idp-review-profile	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	a50deba1-d6ba-4a1b-b73d-e30c97810dbe	0	10	f	\N	030e09ea-bdc7-4164-8856-ea4fc271be1c
0594b3c9-7be3-4311-8c8d-33b214ce5fac	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	a50deba1-d6ba-4a1b-b73d-e30c97810dbe	0	20	t	62e338a5-e23d-4751-8e3b-e12c2422a061	\N
755aa7b2-75c4-4af6-b1ce-b2b94809982d	\N	idp-create-user-if-unique	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	62e338a5-e23d-4751-8e3b-e12c2422a061	2	10	f	\N	b0ba2b31-18ee-4372-a442-8dffe65a03fe
ca04ff42-9b7e-43c1-aa6d-4b7de03c4aa1	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	62e338a5-e23d-4751-8e3b-e12c2422a061	2	20	t	540f465d-2cc5-41dc-9cc9-5bd9bb83f5d8	\N
d9a5d922-0222-490b-905f-454be9e92839	\N	idp-confirm-link	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	540f465d-2cc5-41dc-9cc9-5bd9bb83f5d8	0	10	f	\N	\N
650358dc-d021-4871-aa63-fa45a111592c	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	540f465d-2cc5-41dc-9cc9-5bd9bb83f5d8	0	20	t	6b92d722-8227-4f69-8663-c7124e1c5a92	\N
43cd35db-e83c-4a4e-a79c-c7b5056d1bd9	\N	idp-email-verification	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	6b92d722-8227-4f69-8663-c7124e1c5a92	2	10	f	\N	\N
92880429-94ff-4616-91a0-664e1e13d973	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	6b92d722-8227-4f69-8663-c7124e1c5a92	2	20	t	0081f8a5-f6d9-4635-8eb4-d924b26b528d	\N
01b7419c-e380-4f07-9200-a186a3e09dec	\N	idp-username-password-form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0081f8a5-f6d9-4635-8eb4-d924b26b528d	0	10	f	\N	\N
3b4b65a4-2ade-4cca-b4c1-3b5a72ba14ea	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	0081f8a5-f6d9-4635-8eb4-d924b26b528d	1	20	t	18c0706b-5e24-4911-9f65-8ff08bf94356	\N
deb1b804-e436-49b2-8b62-c4010db6aa43	\N	conditional-user-configured	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	18c0706b-5e24-4911-9f65-8ff08bf94356	0	10	f	\N	\N
62470b3d-5791-4fa2-852d-eae81a011bec	\N	auth-otp-form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	18c0706b-5e24-4911-9f65-8ff08bf94356	0	20	f	\N	\N
7b54aef3-7f9d-4900-8921-4e07c23f167f	\N	http-basic-authenticator	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b860d4ae-b737-4388-8cb2-aaf2e8f7c516	0	10	f	\N	\N
4d4d685c-25be-403c-a033-e62e8e6fe40f	\N	docker-http-basic-authenticator	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	b55b3700-7400-4d72-ab70-ca291b03af2c	0	10	f	\N	\N
21a46d05-2b17-4cdf-863e-156605eee73b	\N	auth-cookie	192c7eba-98c5-4d87-9f5f-059ac8515a9f	655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	2	10	f	\N	\N
d4fe4f5f-fa53-434f-90d1-1a5030e43d3c	\N	auth-spnego	192c7eba-98c5-4d87-9f5f-059ac8515a9f	655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	3	20	f	\N	\N
cf4da80b-42a3-4f26-a5a9-75a72f0f0b25	\N	identity-provider-redirector	192c7eba-98c5-4d87-9f5f-059ac8515a9f	655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	2	25	f	\N	\N
45e51175-7580-4171-bfbd-00f395b0d2b6	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	2	30	t	42ba523b-da84-43b2-a1bf-846bc323e41f	\N
92bf4a48-969a-4701-9a1a-5095d5f7a771	\N	auth-username-password-form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	42ba523b-da84-43b2-a1bf-846bc323e41f	0	10	f	\N	\N
8599f576-7c4d-414e-a6c7-dbfddfc78367	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	42ba523b-da84-43b2-a1bf-846bc323e41f	1	20	t	a2f1b3d1-5d29-4a46-876c-e4e3775353f9	\N
13c0e47c-8e10-441f-84f6-6bd4857c911e	\N	conditional-user-configured	192c7eba-98c5-4d87-9f5f-059ac8515a9f	a2f1b3d1-5d29-4a46-876c-e4e3775353f9	0	10	f	\N	\N
fe8cd028-5ce5-45a6-b0cc-6a5fe6f1265c	\N	auth-otp-form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	a2f1b3d1-5d29-4a46-876c-e4e3775353f9	0	20	f	\N	\N
6c098bf7-bc71-4556-8f36-839f54213b96	\N	direct-grant-validate-username	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7b8d49df-024a-4b85-81f0-069c60e8709a	0	10	f	\N	\N
afb4e132-c260-4178-aa84-124bc66bbcdb	\N	direct-grant-validate-password	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7b8d49df-024a-4b85-81f0-069c60e8709a	0	20	f	\N	\N
9ce78ab6-b25c-445c-aa8d-fdfc80bcb132	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7b8d49df-024a-4b85-81f0-069c60e8709a	1	30	t	58a563bf-abfd-42ac-9459-e33cc1fd943d	\N
c70c7f20-2246-4c36-84ef-0c972a800a41	\N	conditional-user-configured	192c7eba-98c5-4d87-9f5f-059ac8515a9f	58a563bf-abfd-42ac-9459-e33cc1fd943d	0	10	f	\N	\N
82f669b6-a489-4d4e-996b-d2cb3ff0b11b	\N	direct-grant-validate-otp	192c7eba-98c5-4d87-9f5f-059ac8515a9f	58a563bf-abfd-42ac-9459-e33cc1fd943d	0	20	f	\N	\N
65e21f6f-2a90-4e53-a618-3bdfcca9d6f4	\N	registration-page-form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	519e4a95-50cf-47d1-acde-02dd118e38b0	0	10	t	7ca62057-0a0b-4ce7-b601-94f60d4a2feb	\N
68830f97-77ab-4a2a-b10e-14034ef9a6ee	\N	registration-user-creation	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7ca62057-0a0b-4ce7-b601-94f60d4a2feb	0	20	f	\N	\N
87dde8ed-29fd-44de-927c-83fc28d7e42e	\N	registration-profile-action	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7ca62057-0a0b-4ce7-b601-94f60d4a2feb	0	40	f	\N	\N
dc66ab55-70a1-4d8a-9971-a3a81d3ec7c6	\N	registration-password-action	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7ca62057-0a0b-4ce7-b601-94f60d4a2feb	0	50	f	\N	\N
b4e77d7a-f9ec-4292-a399-7e7d1607e4b1	\N	registration-recaptcha-action	192c7eba-98c5-4d87-9f5f-059ac8515a9f	7ca62057-0a0b-4ce7-b601-94f60d4a2feb	3	60	f	\N	\N
c34f6262-f6f7-4969-9c6e-1a8d9cf01086	\N	reset-credentials-choose-user	192c7eba-98c5-4d87-9f5f-059ac8515a9f	fe832423-ee2e-4105-ad54-2172427ec038	0	10	f	\N	\N
299140ba-2e55-403b-9d56-43e4abf315a2	\N	reset-credential-email	192c7eba-98c5-4d87-9f5f-059ac8515a9f	fe832423-ee2e-4105-ad54-2172427ec038	0	20	f	\N	\N
c3d411be-aa76-4991-8ed1-ff2bb9ec4f36	\N	reset-password	192c7eba-98c5-4d87-9f5f-059ac8515a9f	fe832423-ee2e-4105-ad54-2172427ec038	0	30	f	\N	\N
245c813e-9cdd-425d-9090-f553f186e8cb	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	fe832423-ee2e-4105-ad54-2172427ec038	1	40	t	de466c44-5569-4c55-92bf-4b439207e44a	\N
af754e93-5e77-4b3d-b2b3-84d08393219e	\N	conditional-user-configured	192c7eba-98c5-4d87-9f5f-059ac8515a9f	de466c44-5569-4c55-92bf-4b439207e44a	0	10	f	\N	\N
f2ee5c20-8b1e-4a20-808a-07a135a534f0	\N	reset-otp	192c7eba-98c5-4d87-9f5f-059ac8515a9f	de466c44-5569-4c55-92bf-4b439207e44a	0	20	f	\N	\N
82b11c52-6829-49c3-81e5-f95f79fd9211	\N	client-secret	192c7eba-98c5-4d87-9f5f-059ac8515a9f	74053835-0f48-4577-843f-ed24711091f7	2	10	f	\N	\N
658a44ed-5211-429c-9c8f-37df242d35b6	\N	client-jwt	192c7eba-98c5-4d87-9f5f-059ac8515a9f	74053835-0f48-4577-843f-ed24711091f7	2	20	f	\N	\N
8118f42a-8e1b-4804-9acf-2474b34daf0e	\N	client-secret-jwt	192c7eba-98c5-4d87-9f5f-059ac8515a9f	74053835-0f48-4577-843f-ed24711091f7	2	30	f	\N	\N
48744db9-634a-4407-a90d-d3be219db5f6	\N	client-x509	192c7eba-98c5-4d87-9f5f-059ac8515a9f	74053835-0f48-4577-843f-ed24711091f7	2	40	f	\N	\N
2b9c4bf9-cd93-4a0b-b976-8e5eb6a88aba	\N	idp-review-profile	192c7eba-98c5-4d87-9f5f-059ac8515a9f	2d9903c0-e8d9-4072-b183-1047b20c2d92	0	10	f	\N	5bdbc228-dd71-466f-9a25-17be9448e6e1
88750843-f22e-4904-bcad-59afd0a9e260	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	2d9903c0-e8d9-4072-b183-1047b20c2d92	0	20	t	70e209b0-4844-49b1-b1f5-5c3e5e196e17	\N
2a37d601-c6a8-44ad-89a6-2a802c57d037	\N	idp-create-user-if-unique	192c7eba-98c5-4d87-9f5f-059ac8515a9f	70e209b0-4844-49b1-b1f5-5c3e5e196e17	2	10	f	\N	17313df8-0ee6-4e77-b412-cd93f1dcb2ba
5a1d66ff-2fab-4a65-9504-802f4c315ee3	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	70e209b0-4844-49b1-b1f5-5c3e5e196e17	2	20	t	81bcd6cb-bced-4bf9-87a0-2f75c854a85e	\N
3512586a-0d71-4b79-a7f6-70b223c98bbf	\N	idp-confirm-link	192c7eba-98c5-4d87-9f5f-059ac8515a9f	81bcd6cb-bced-4bf9-87a0-2f75c854a85e	0	10	f	\N	\N
0ec50e55-77e5-42a7-ad62-dc03c6adefef	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	81bcd6cb-bced-4bf9-87a0-2f75c854a85e	0	20	t	1da2d937-cf62-4d6c-a333-144ddd88413c	\N
2c2fd0f4-6697-41aa-9229-4533a627e316	\N	idp-email-verification	192c7eba-98c5-4d87-9f5f-059ac8515a9f	1da2d937-cf62-4d6c-a333-144ddd88413c	2	10	f	\N	\N
7d5a3caf-df2a-4546-bb4d-6f58b7df7cdd	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	1da2d937-cf62-4d6c-a333-144ddd88413c	2	20	t	89700391-125e-447d-b977-df63c188abdf	\N
6d102882-294c-422b-9d53-aadd6f6518e0	\N	idp-username-password-form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	89700391-125e-447d-b977-df63c188abdf	0	10	f	\N	\N
32696293-3875-4335-83b2-f26ae30b3ae4	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	89700391-125e-447d-b977-df63c188abdf	1	20	t	1d640d36-d8c5-4184-a46b-25189e980f6c	\N
d324c469-3650-431a-9c12-5dbe77bbb89a	\N	conditional-user-configured	192c7eba-98c5-4d87-9f5f-059ac8515a9f	1d640d36-d8c5-4184-a46b-25189e980f6c	0	10	f	\N	\N
ef70a335-bbed-4f45-9b3d-c9999b852787	\N	auth-otp-form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	1d640d36-d8c5-4184-a46b-25189e980f6c	0	20	f	\N	\N
aed2abee-3c0e-4661-a098-fc971c2e1fce	\N	http-basic-authenticator	192c7eba-98c5-4d87-9f5f-059ac8515a9f	11c6cc5e-b9b9-483d-8faa-a303ac09aed7	0	10	f	\N	\N
bcdaa71f-24f7-4c20-aa62-b3520bce0bbd	\N	docker-http-basic-authenticator	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f1004845-6e8d-4138-9b1e-d98774accaf2	0	10	f	\N	\N
\.


--
-- Data for Name: authentication_flow; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.authentication_flow (id, alias, description, realm_id, provider_id, top_level, built_in) FROM stdin;
261ee39e-ad77-4d9d-8e56-15ec77ea611b	browser	browser based authentication	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
f3dbb7c6-92ab-4824-9081-43d2c475a949	forms	Username, password, otp and other auth forms.	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
b16e2cfc-d6d9-4b17-b58f-482dd04b7474	Browser - Conditional OTP	Flow to determine if the OTP is required for the authentication	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
b31ebba6-89c4-4d34-bd26-18f958560753	direct grant	OpenID Connect Resource Owner Grant	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
a031f3e8-d5fd-4677-937e-884c23b9d7f9	Direct Grant - Conditional OTP	Flow to determine if the OTP is required for the authentication	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
071c0a54-e2e9-4791-bb7e-72853915e371	registration	registration flow	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
7700368f-d112-477a-aeb4-675f0bafff41	registration form	registration form	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	form-flow	f	t
0b110242-a5a9-40bd-8ac7-78fec175f3b8	reset credentials	Reset credentials for a user if they forgot their password or something	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
82800697-006e-458e-881d-9bef7a683964	Reset - Conditional OTP	Flow to determine if the OTP should be reset or not. Set to REQUIRED to force.	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
ecb294d1-bb2c-458b-96e6-257a74ee42de	clients	Base authentication for clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	client-flow	t	t
a50deba1-d6ba-4a1b-b73d-e30c97810dbe	first broker login	Actions taken after first broker login with identity provider account, which is not yet linked to any Keycloak account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
62e338a5-e23d-4751-8e3b-e12c2422a061	User creation or linking	Flow for the existing/non-existing user alternatives	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
540f465d-2cc5-41dc-9cc9-5bd9bb83f5d8	Handle Existing Account	Handle what to do if there is existing account with same email/username like authenticated identity provider	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
6b92d722-8227-4f69-8663-c7124e1c5a92	Account verification options	Method with which to verity the existing account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
0081f8a5-f6d9-4635-8eb4-d924b26b528d	Verify Existing Account by Re-authentication	Reauthentication of existing account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
18c0706b-5e24-4911-9f65-8ff08bf94356	First broker login - Conditional OTP	Flow to determine if the OTP is required for the authentication	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	f	t
b860d4ae-b737-4388-8cb2-aaf2e8f7c516	saml ecp	SAML ECP Profile Authentication Flow	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
b55b3700-7400-4d72-ab70-ca291b03af2c	docker auth	Used by Docker clients to authenticate against the IDP	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	basic-flow	t	t
655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	browser	browser based authentication	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
42ba523b-da84-43b2-a1bf-846bc323e41f	forms	Username, password, otp and other auth forms.	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
a2f1b3d1-5d29-4a46-876c-e4e3775353f9	Browser - Conditional OTP	Flow to determine if the OTP is required for the authentication	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
7b8d49df-024a-4b85-81f0-069c60e8709a	direct grant	OpenID Connect Resource Owner Grant	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
58a563bf-abfd-42ac-9459-e33cc1fd943d	Direct Grant - Conditional OTP	Flow to determine if the OTP is required for the authentication	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
519e4a95-50cf-47d1-acde-02dd118e38b0	registration	registration flow	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
7ca62057-0a0b-4ce7-b601-94f60d4a2feb	registration form	registration form	192c7eba-98c5-4d87-9f5f-059ac8515a9f	form-flow	f	t
fe832423-ee2e-4105-ad54-2172427ec038	reset credentials	Reset credentials for a user if they forgot their password or something	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
de466c44-5569-4c55-92bf-4b439207e44a	Reset - Conditional OTP	Flow to determine if the OTP should be reset or not. Set to REQUIRED to force.	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
74053835-0f48-4577-843f-ed24711091f7	clients	Base authentication for clients	192c7eba-98c5-4d87-9f5f-059ac8515a9f	client-flow	t	t
2d9903c0-e8d9-4072-b183-1047b20c2d92	first broker login	Actions taken after first broker login with identity provider account, which is not yet linked to any Keycloak account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
70e209b0-4844-49b1-b1f5-5c3e5e196e17	User creation or linking	Flow for the existing/non-existing user alternatives	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
81bcd6cb-bced-4bf9-87a0-2f75c854a85e	Handle Existing Account	Handle what to do if there is existing account with same email/username like authenticated identity provider	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
1da2d937-cf62-4d6c-a333-144ddd88413c	Account verification options	Method with which to verity the existing account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
89700391-125e-447d-b977-df63c188abdf	Verify Existing Account by Re-authentication	Reauthentication of existing account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
1d640d36-d8c5-4184-a46b-25189e980f6c	First broker login - Conditional OTP	Flow to determine if the OTP is required for the authentication	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	f	t
11c6cc5e-b9b9-483d-8faa-a303ac09aed7	saml ecp	SAML ECP Profile Authentication Flow	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
f1004845-6e8d-4138-9b1e-d98774accaf2	docker auth	Used by Docker clients to authenticate against the IDP	192c7eba-98c5-4d87-9f5f-059ac8515a9f	basic-flow	t	t
\.


--
-- Data for Name: authenticator_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.authenticator_config (id, alias, realm_id) FROM stdin;
030e09ea-bdc7-4164-8856-ea4fc271be1c	review profile config	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff
b0ba2b31-18ee-4372-a442-8dffe65a03fe	create unique user config	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff
5bdbc228-dd71-466f-9a25-17be9448e6e1	review profile config	192c7eba-98c5-4d87-9f5f-059ac8515a9f
17313df8-0ee6-4e77-b412-cd93f1dcb2ba	create unique user config	192c7eba-98c5-4d87-9f5f-059ac8515a9f
\.


--
-- Data for Name: authenticator_config_entry; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.authenticator_config_entry (authenticator_id, value, name) FROM stdin;
030e09ea-bdc7-4164-8856-ea4fc271be1c	missing	update.profile.on.first.login
b0ba2b31-18ee-4372-a442-8dffe65a03fe	false	require.password.update.after.registration
17313df8-0ee6-4e77-b412-cd93f1dcb2ba	false	require.password.update.after.registration
5bdbc228-dd71-466f-9a25-17be9448e6e1	missing	update.profile.on.first.login
\.


--
-- Data for Name: broker_link; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.broker_link (identity_provider, storage_provider_id, realm_id, broker_user_id, broker_username, token, user_id) FROM stdin;
\.


--
-- Data for Name: client; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client (id, enabled, full_scope_allowed, client_id, not_before, public_client, secret, base_url, bearer_only, management_url, surrogate_auth_required, realm_id, protocol, node_rereg_timeout, frontchannel_logout, consent_required, name, service_accounts_enabled, client_authenticator_type, root_url, description, registration_token, standard_flow_enabled, implicit_flow_enabled, direct_access_grants_enabled, always_display_in_console) FROM stdin;
7054aec7-dafe-46ea-b752-855f1626b97a	t	f	master-realm	0	f	\N	\N	t	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	0	f	f	master Realm	f	client-secret	\N	\N	\N	t	f	f	f
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	f	account	0	t	\N	/realms/master/account/	f	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	openid-connect	0	f	f	${client_account}	f	client-secret	${authBaseUrl}	\N	\N	t	f	f	f
b42513aa-047e-4187-9fd7-7ce4137e3206	t	f	account-console	0	t	\N	/realms/master/account/	f	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	openid-connect	0	f	f	${client_account-console}	f	client-secret	${authBaseUrl}	\N	\N	t	f	f	f
61987548-33ab-4959-9fd7-9b3bc2cb3e79	t	f	broker	0	f	\N	\N	t	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	openid-connect	0	f	f	${client_broker}	f	client-secret	\N	\N	\N	t	f	f	f
ffa621f0-3e6c-477d-86da-eb2186eb1f40	t	f	security-admin-console	0	t	\N	/admin/master/console/	f	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	openid-connect	0	f	f	${client_security-admin-console}	f	client-secret	${authAdminUrl}	\N	\N	t	f	f	f
7b563a50-0ad9-4aab-8390-505319a2e47d	t	f	admin-cli	0	t	\N	\N	f	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	openid-connect	0	f	f	${client_admin-cli}	f	client-secret	\N	\N	\N	f	f	t	f
4528294a-48c5-4295-ba48-015c67ad0632	t	f	logprep-realm	0	f	\N	\N	t	\N	f	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	0	f	f	logprep Realm	f	client-secret	\N	\N	\N	t	f	f	f
91109a48-1062-4ca1-a7e6-b511be738faa	t	f	realm-management	0	f	\N	\N	t	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_realm-management}	f	client-secret	\N	\N	\N	t	f	f	f
713208be-0b29-4727-abc0-1c5102bf0c0e	t	f	account	0	t	\N	/realms/logprep/account/	f	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_account}	f	client-secret	${authBaseUrl}	\N	\N	t	f	f	f
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	t	f	account-console	0	t	\N	/realms/logprep/account/	f	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_account-console}	f	client-secret	${authBaseUrl}	\N	\N	t	f	f	f
26ef3d61-6c70-487b-b633-c7f798f0f4a5	t	f	broker	0	f	\N	\N	t	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_broker}	f	client-secret	\N	\N	\N	t	f	f	f
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	t	f	security-admin-console	0	t	\N	/admin/logprep/console/	f	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_security-admin-console}	f	client-secret	${authAdminUrl}	\N	\N	t	f	f	f
33cc2652-d986-45b4-9ac6-7a5a60765251	t	f	admin-cli	0	t	\N	\N	f	\N	f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	0	f	f	${client_admin-cli}	f	client-secret	\N	\N	\N	f	f	t	f
05b15c96-ddea-483c-9cd2-0c16d86aefac	t	t	fda-backend	0	f	Kh4tz3wMcBMrPdGVuQeOv3aTlPKpQfOw		f		f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	-1	t	f		f	client-secret			\N	t	f	t	f
02d1898e-b586-4795-b3ff-fd2bae926af0	t	t	fda	0	t	\N	http://localhost:8002	f		f	192c7eba-98c5-4d87-9f5f-059ac8515a9f	openid-connect	-1	t	f		f	client-secret			\N	t	f	t	f
\.


--
-- Data for Name: client_attributes; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_attributes (client_id, name, value) FROM stdin;
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	post.logout.redirect.uris	+
b42513aa-047e-4187-9fd7-7ce4137e3206	post.logout.redirect.uris	+
b42513aa-047e-4187-9fd7-7ce4137e3206	pkce.code.challenge.method	S256
ffa621f0-3e6c-477d-86da-eb2186eb1f40	post.logout.redirect.uris	+
ffa621f0-3e6c-477d-86da-eb2186eb1f40	pkce.code.challenge.method	S256
713208be-0b29-4727-abc0-1c5102bf0c0e	post.logout.redirect.uris	+
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	post.logout.redirect.uris	+
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	pkce.code.challenge.method	S256
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	post.logout.redirect.uris	+
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	pkce.code.challenge.method	S256
02d1898e-b586-4795-b3ff-fd2bae926af0	oauth2.device.authorization.grant.enabled	false
02d1898e-b586-4795-b3ff-fd2bae926af0	oidc.ciba.grant.enabled	false
02d1898e-b586-4795-b3ff-fd2bae926af0	backchannel.logout.session.required	true
02d1898e-b586-4795-b3ff-fd2bae926af0	backchannel.logout.revoke.offline.tokens	false
02d1898e-b586-4795-b3ff-fd2bae926af0	display.on.consent.screen	false
05b15c96-ddea-483c-9cd2-0c16d86aefac	client.secret.creation.time	1700562889
05b15c96-ddea-483c-9cd2-0c16d86aefac	oauth2.device.authorization.grant.enabled	false
05b15c96-ddea-483c-9cd2-0c16d86aefac	oidc.ciba.grant.enabled	false
05b15c96-ddea-483c-9cd2-0c16d86aefac	backchannel.logout.session.required	true
05b15c96-ddea-483c-9cd2-0c16d86aefac	backchannel.logout.revoke.offline.tokens	false
\.


--
-- Data for Name: client_auth_flow_bindings; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_auth_flow_bindings (client_id, flow_id, binding_name) FROM stdin;
\.


--
-- Data for Name: client_initial_access; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_initial_access (id, realm_id, "timestamp", expiration, count, remaining_count) FROM stdin;
\.


--
-- Data for Name: client_node_registrations; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_node_registrations (client_id, value, name) FROM stdin;
\.


--
-- Data for Name: client_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_scope (id, name, realm_id, description, protocol) FROM stdin;
84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	offline_access	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect built-in scope: offline_access	openid-connect
fc5549c1-0bd7-42bb-8002-7035958cdeec	role_list	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	SAML role list	saml
14112e9d-14fa-433d-8ae8-888fbdebe398	profile	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect built-in scope: profile	openid-connect
d5c24ac1-3538-467f-b560-a2ff345836bd	email	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect built-in scope: email	openid-connect
571511e6-0111-405d-b39a-271aefbad4db	address	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect built-in scope: address	openid-connect
4c37fde1-2d9e-4b63-8277-8274622c8bd6	phone	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect built-in scope: phone	openid-connect
bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	roles	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect scope for add user roles to the access token	openid-connect
c53e2a13-a31f-4ce0-9560-2e07e67d645b	web-origins	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect scope for add allowed web origins to the access token	openid-connect
349d7526-4813-42e2-abd0-88d762b0784e	microprofile-jwt	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	Microprofile - JWT built-in scope	openid-connect
ba412952-1281-4492-89fe-c8cb7e69f6be	acr	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	OpenID Connect scope for add acr (authentication context class reference) to the token	openid-connect
216afde5-8285-439c-a6ff-109667682532	offline_access	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect built-in scope: offline_access	openid-connect
3bb50451-f5b6-470c-b9ef-f56947982bce	role_list	192c7eba-98c5-4d87-9f5f-059ac8515a9f	SAML role list	saml
29874bd4-37d5-4d8e-a70d-35fac7b7316f	profile	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect built-in scope: profile	openid-connect
b633de75-729d-421f-afe5-06381d531a7d	email	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect built-in scope: email	openid-connect
322bb55b-9c86-405c-bc4b-4e95d1f9f020	address	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect built-in scope: address	openid-connect
bac6e34a-8ddc-456e-ada2-65c62aa4eac9	phone	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect built-in scope: phone	openid-connect
bc4cb0cb-9821-4678-b147-caebf705b629	roles	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect scope for add user roles to the access token	openid-connect
b276f043-6971-4544-968d-45b83a8fd024	web-origins	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect scope for add allowed web origins to the access token	openid-connect
43a600c5-7c41-4436-b3f4-8c6a1b066348	microprofile-jwt	192c7eba-98c5-4d87-9f5f-059ac8515a9f	Microprofile - JWT built-in scope	openid-connect
40669fe7-d52a-4039-8da6-bf09ce2f1907	acr	192c7eba-98c5-4d87-9f5f-059ac8515a9f	OpenID Connect scope for add acr (authentication context class reference) to the token	openid-connect
\.


--
-- Data for Name: client_scope_attributes; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_scope_attributes (scope_id, value, name) FROM stdin;
84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	true	display.on.consent.screen
84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	${offlineAccessScopeConsentText}	consent.screen.text
fc5549c1-0bd7-42bb-8002-7035958cdeec	true	display.on.consent.screen
fc5549c1-0bd7-42bb-8002-7035958cdeec	${samlRoleListScopeConsentText}	consent.screen.text
14112e9d-14fa-433d-8ae8-888fbdebe398	true	display.on.consent.screen
14112e9d-14fa-433d-8ae8-888fbdebe398	${profileScopeConsentText}	consent.screen.text
14112e9d-14fa-433d-8ae8-888fbdebe398	true	include.in.token.scope
d5c24ac1-3538-467f-b560-a2ff345836bd	true	display.on.consent.screen
d5c24ac1-3538-467f-b560-a2ff345836bd	${emailScopeConsentText}	consent.screen.text
d5c24ac1-3538-467f-b560-a2ff345836bd	true	include.in.token.scope
571511e6-0111-405d-b39a-271aefbad4db	true	display.on.consent.screen
571511e6-0111-405d-b39a-271aefbad4db	${addressScopeConsentText}	consent.screen.text
571511e6-0111-405d-b39a-271aefbad4db	true	include.in.token.scope
4c37fde1-2d9e-4b63-8277-8274622c8bd6	true	display.on.consent.screen
4c37fde1-2d9e-4b63-8277-8274622c8bd6	${phoneScopeConsentText}	consent.screen.text
4c37fde1-2d9e-4b63-8277-8274622c8bd6	true	include.in.token.scope
bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	true	display.on.consent.screen
bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	${rolesScopeConsentText}	consent.screen.text
bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	false	include.in.token.scope
c53e2a13-a31f-4ce0-9560-2e07e67d645b	false	display.on.consent.screen
c53e2a13-a31f-4ce0-9560-2e07e67d645b		consent.screen.text
c53e2a13-a31f-4ce0-9560-2e07e67d645b	false	include.in.token.scope
349d7526-4813-42e2-abd0-88d762b0784e	false	display.on.consent.screen
349d7526-4813-42e2-abd0-88d762b0784e	true	include.in.token.scope
ba412952-1281-4492-89fe-c8cb7e69f6be	false	display.on.consent.screen
ba412952-1281-4492-89fe-c8cb7e69f6be	false	include.in.token.scope
216afde5-8285-439c-a6ff-109667682532	true	display.on.consent.screen
216afde5-8285-439c-a6ff-109667682532	${offlineAccessScopeConsentText}	consent.screen.text
3bb50451-f5b6-470c-b9ef-f56947982bce	true	display.on.consent.screen
3bb50451-f5b6-470c-b9ef-f56947982bce	${samlRoleListScopeConsentText}	consent.screen.text
29874bd4-37d5-4d8e-a70d-35fac7b7316f	true	display.on.consent.screen
29874bd4-37d5-4d8e-a70d-35fac7b7316f	${profileScopeConsentText}	consent.screen.text
29874bd4-37d5-4d8e-a70d-35fac7b7316f	true	include.in.token.scope
b633de75-729d-421f-afe5-06381d531a7d	true	display.on.consent.screen
b633de75-729d-421f-afe5-06381d531a7d	${emailScopeConsentText}	consent.screen.text
b633de75-729d-421f-afe5-06381d531a7d	true	include.in.token.scope
322bb55b-9c86-405c-bc4b-4e95d1f9f020	true	display.on.consent.screen
322bb55b-9c86-405c-bc4b-4e95d1f9f020	${addressScopeConsentText}	consent.screen.text
322bb55b-9c86-405c-bc4b-4e95d1f9f020	true	include.in.token.scope
bac6e34a-8ddc-456e-ada2-65c62aa4eac9	true	display.on.consent.screen
bac6e34a-8ddc-456e-ada2-65c62aa4eac9	${phoneScopeConsentText}	consent.screen.text
bac6e34a-8ddc-456e-ada2-65c62aa4eac9	true	include.in.token.scope
bc4cb0cb-9821-4678-b147-caebf705b629	true	display.on.consent.screen
bc4cb0cb-9821-4678-b147-caebf705b629	${rolesScopeConsentText}	consent.screen.text
bc4cb0cb-9821-4678-b147-caebf705b629	false	include.in.token.scope
b276f043-6971-4544-968d-45b83a8fd024	false	display.on.consent.screen
b276f043-6971-4544-968d-45b83a8fd024		consent.screen.text
b276f043-6971-4544-968d-45b83a8fd024	false	include.in.token.scope
43a600c5-7c41-4436-b3f4-8c6a1b066348	false	display.on.consent.screen
43a600c5-7c41-4436-b3f4-8c6a1b066348	true	include.in.token.scope
40669fe7-d52a-4039-8da6-bf09ce2f1907	false	display.on.consent.screen
40669fe7-d52a-4039-8da6-bf09ce2f1907	false	include.in.token.scope
\.


--
-- Data for Name: client_scope_client; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_scope_client (client_id, scope_id, default_scope) FROM stdin;
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	ba412952-1281-4492-89fe-c8cb7e69f6be	t
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	14112e9d-14fa-433d-8ae8-888fbdebe398	t
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	d5c24ac1-3538-467f-b560-a2ff345836bd	t
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	571511e6-0111-405d-b39a-271aefbad4db	f
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	349d7526-4813-42e2-abd0-88d762b0784e	f
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
b42513aa-047e-4187-9fd7-7ce4137e3206	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
b42513aa-047e-4187-9fd7-7ce4137e3206	ba412952-1281-4492-89fe-c8cb7e69f6be	t
b42513aa-047e-4187-9fd7-7ce4137e3206	14112e9d-14fa-433d-8ae8-888fbdebe398	t
b42513aa-047e-4187-9fd7-7ce4137e3206	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
b42513aa-047e-4187-9fd7-7ce4137e3206	d5c24ac1-3538-467f-b560-a2ff345836bd	t
b42513aa-047e-4187-9fd7-7ce4137e3206	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
b42513aa-047e-4187-9fd7-7ce4137e3206	571511e6-0111-405d-b39a-271aefbad4db	f
b42513aa-047e-4187-9fd7-7ce4137e3206	349d7526-4813-42e2-abd0-88d762b0784e	f
b42513aa-047e-4187-9fd7-7ce4137e3206	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
7b563a50-0ad9-4aab-8390-505319a2e47d	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
7b563a50-0ad9-4aab-8390-505319a2e47d	ba412952-1281-4492-89fe-c8cb7e69f6be	t
7b563a50-0ad9-4aab-8390-505319a2e47d	14112e9d-14fa-433d-8ae8-888fbdebe398	t
7b563a50-0ad9-4aab-8390-505319a2e47d	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
7b563a50-0ad9-4aab-8390-505319a2e47d	d5c24ac1-3538-467f-b560-a2ff345836bd	t
7b563a50-0ad9-4aab-8390-505319a2e47d	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
7b563a50-0ad9-4aab-8390-505319a2e47d	571511e6-0111-405d-b39a-271aefbad4db	f
7b563a50-0ad9-4aab-8390-505319a2e47d	349d7526-4813-42e2-abd0-88d762b0784e	f
7b563a50-0ad9-4aab-8390-505319a2e47d	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
61987548-33ab-4959-9fd7-9b3bc2cb3e79	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
61987548-33ab-4959-9fd7-9b3bc2cb3e79	ba412952-1281-4492-89fe-c8cb7e69f6be	t
61987548-33ab-4959-9fd7-9b3bc2cb3e79	14112e9d-14fa-433d-8ae8-888fbdebe398	t
61987548-33ab-4959-9fd7-9b3bc2cb3e79	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
61987548-33ab-4959-9fd7-9b3bc2cb3e79	d5c24ac1-3538-467f-b560-a2ff345836bd	t
61987548-33ab-4959-9fd7-9b3bc2cb3e79	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
61987548-33ab-4959-9fd7-9b3bc2cb3e79	571511e6-0111-405d-b39a-271aefbad4db	f
61987548-33ab-4959-9fd7-9b3bc2cb3e79	349d7526-4813-42e2-abd0-88d762b0784e	f
61987548-33ab-4959-9fd7-9b3bc2cb3e79	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
7054aec7-dafe-46ea-b752-855f1626b97a	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
7054aec7-dafe-46ea-b752-855f1626b97a	ba412952-1281-4492-89fe-c8cb7e69f6be	t
7054aec7-dafe-46ea-b752-855f1626b97a	14112e9d-14fa-433d-8ae8-888fbdebe398	t
7054aec7-dafe-46ea-b752-855f1626b97a	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
7054aec7-dafe-46ea-b752-855f1626b97a	d5c24ac1-3538-467f-b560-a2ff345836bd	t
7054aec7-dafe-46ea-b752-855f1626b97a	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
7054aec7-dafe-46ea-b752-855f1626b97a	571511e6-0111-405d-b39a-271aefbad4db	f
7054aec7-dafe-46ea-b752-855f1626b97a	349d7526-4813-42e2-abd0-88d762b0784e	f
7054aec7-dafe-46ea-b752-855f1626b97a	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
ffa621f0-3e6c-477d-86da-eb2186eb1f40	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
ffa621f0-3e6c-477d-86da-eb2186eb1f40	ba412952-1281-4492-89fe-c8cb7e69f6be	t
ffa621f0-3e6c-477d-86da-eb2186eb1f40	14112e9d-14fa-433d-8ae8-888fbdebe398	t
ffa621f0-3e6c-477d-86da-eb2186eb1f40	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
ffa621f0-3e6c-477d-86da-eb2186eb1f40	d5c24ac1-3538-467f-b560-a2ff345836bd	t
ffa621f0-3e6c-477d-86da-eb2186eb1f40	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
ffa621f0-3e6c-477d-86da-eb2186eb1f40	571511e6-0111-405d-b39a-271aefbad4db	f
ffa621f0-3e6c-477d-86da-eb2186eb1f40	349d7526-4813-42e2-abd0-88d762b0784e	f
ffa621f0-3e6c-477d-86da-eb2186eb1f40	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
713208be-0b29-4727-abc0-1c5102bf0c0e	bc4cb0cb-9821-4678-b147-caebf705b629	t
713208be-0b29-4727-abc0-1c5102bf0c0e	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
713208be-0b29-4727-abc0-1c5102bf0c0e	b633de75-729d-421f-afe5-06381d531a7d	t
713208be-0b29-4727-abc0-1c5102bf0c0e	b276f043-6971-4544-968d-45b83a8fd024	t
713208be-0b29-4727-abc0-1c5102bf0c0e	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
713208be-0b29-4727-abc0-1c5102bf0c0e	216afde5-8285-439c-a6ff-109667682532	f
713208be-0b29-4727-abc0-1c5102bf0c0e	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
713208be-0b29-4727-abc0-1c5102bf0c0e	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
713208be-0b29-4727-abc0-1c5102bf0c0e	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	bc4cb0cb-9821-4678-b147-caebf705b629	t
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	b633de75-729d-421f-afe5-06381d531a7d	t
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	b276f043-6971-4544-968d-45b83a8fd024	t
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	216afde5-8285-439c-a6ff-109667682532	f
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
33cc2652-d986-45b4-9ac6-7a5a60765251	bc4cb0cb-9821-4678-b147-caebf705b629	t
33cc2652-d986-45b4-9ac6-7a5a60765251	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
33cc2652-d986-45b4-9ac6-7a5a60765251	b633de75-729d-421f-afe5-06381d531a7d	t
33cc2652-d986-45b4-9ac6-7a5a60765251	b276f043-6971-4544-968d-45b83a8fd024	t
33cc2652-d986-45b4-9ac6-7a5a60765251	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
33cc2652-d986-45b4-9ac6-7a5a60765251	216afde5-8285-439c-a6ff-109667682532	f
33cc2652-d986-45b4-9ac6-7a5a60765251	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
33cc2652-d986-45b4-9ac6-7a5a60765251	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
33cc2652-d986-45b4-9ac6-7a5a60765251	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
26ef3d61-6c70-487b-b633-c7f798f0f4a5	bc4cb0cb-9821-4678-b147-caebf705b629	t
26ef3d61-6c70-487b-b633-c7f798f0f4a5	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
26ef3d61-6c70-487b-b633-c7f798f0f4a5	b633de75-729d-421f-afe5-06381d531a7d	t
26ef3d61-6c70-487b-b633-c7f798f0f4a5	b276f043-6971-4544-968d-45b83a8fd024	t
26ef3d61-6c70-487b-b633-c7f798f0f4a5	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
26ef3d61-6c70-487b-b633-c7f798f0f4a5	216afde5-8285-439c-a6ff-109667682532	f
26ef3d61-6c70-487b-b633-c7f798f0f4a5	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
26ef3d61-6c70-487b-b633-c7f798f0f4a5	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
26ef3d61-6c70-487b-b633-c7f798f0f4a5	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
91109a48-1062-4ca1-a7e6-b511be738faa	bc4cb0cb-9821-4678-b147-caebf705b629	t
91109a48-1062-4ca1-a7e6-b511be738faa	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
91109a48-1062-4ca1-a7e6-b511be738faa	b633de75-729d-421f-afe5-06381d531a7d	t
91109a48-1062-4ca1-a7e6-b511be738faa	b276f043-6971-4544-968d-45b83a8fd024	t
91109a48-1062-4ca1-a7e6-b511be738faa	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
91109a48-1062-4ca1-a7e6-b511be738faa	216afde5-8285-439c-a6ff-109667682532	f
91109a48-1062-4ca1-a7e6-b511be738faa	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
91109a48-1062-4ca1-a7e6-b511be738faa	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
91109a48-1062-4ca1-a7e6-b511be738faa	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	bc4cb0cb-9821-4678-b147-caebf705b629	t
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	b633de75-729d-421f-afe5-06381d531a7d	t
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	b276f043-6971-4544-968d-45b83a8fd024	t
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	216afde5-8285-439c-a6ff-109667682532	f
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
02d1898e-b586-4795-b3ff-fd2bae926af0	bc4cb0cb-9821-4678-b147-caebf705b629	t
02d1898e-b586-4795-b3ff-fd2bae926af0	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
02d1898e-b586-4795-b3ff-fd2bae926af0	b633de75-729d-421f-afe5-06381d531a7d	t
02d1898e-b586-4795-b3ff-fd2bae926af0	b276f043-6971-4544-968d-45b83a8fd024	t
02d1898e-b586-4795-b3ff-fd2bae926af0	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
02d1898e-b586-4795-b3ff-fd2bae926af0	216afde5-8285-439c-a6ff-109667682532	f
02d1898e-b586-4795-b3ff-fd2bae926af0	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
02d1898e-b586-4795-b3ff-fd2bae926af0	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
02d1898e-b586-4795-b3ff-fd2bae926af0	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
05b15c96-ddea-483c-9cd2-0c16d86aefac	bc4cb0cb-9821-4678-b147-caebf705b629	t
05b15c96-ddea-483c-9cd2-0c16d86aefac	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
05b15c96-ddea-483c-9cd2-0c16d86aefac	b633de75-729d-421f-afe5-06381d531a7d	t
05b15c96-ddea-483c-9cd2-0c16d86aefac	b276f043-6971-4544-968d-45b83a8fd024	t
05b15c96-ddea-483c-9cd2-0c16d86aefac	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
05b15c96-ddea-483c-9cd2-0c16d86aefac	216afde5-8285-439c-a6ff-109667682532	f
05b15c96-ddea-483c-9cd2-0c16d86aefac	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
05b15c96-ddea-483c-9cd2-0c16d86aefac	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
05b15c96-ddea-483c-9cd2-0c16d86aefac	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
\.


--
-- Data for Name: client_scope_role_mapping; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_scope_role_mapping (scope_id, role_id) FROM stdin;
84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	c16af2bf-5d84-40f4-8b6f-09875cbde07a
216afde5-8285-439c-a6ff-109667682532	f70e4815-0644-49cc-8ea9-c6c87c4afb55
\.


--
-- Data for Name: client_session; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_session (id, client_id, redirect_uri, state, "timestamp", session_id, auth_method, realm_id, auth_user_id, current_action) FROM stdin;
\.


--
-- Data for Name: client_session_auth_status; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_session_auth_status (authenticator, status, client_session) FROM stdin;
\.


--
-- Data for Name: client_session_note; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_session_note (name, value, client_session) FROM stdin;
\.


--
-- Data for Name: client_session_prot_mapper; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_session_prot_mapper (protocol_mapper_id, client_session) FROM stdin;
\.


--
-- Data for Name: client_session_role; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_session_role (role_id, client_session) FROM stdin;
\.


--
-- Data for Name: client_user_session_note; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.client_user_session_note (name, value, client_session) FROM stdin;
\.


--
-- Data for Name: component; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.component (id, name, parent_id, provider_id, provider_type, realm_id, sub_type) FROM stdin;
eac942d9-7640-4467-a5b3-ad255f48238a	Trusted Hosts	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	trusted-hosts	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
ec8d12c8-1252-4d9a-a629-7e63fed7aea4	Consent Required	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	consent-required	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
312a09bd-0afc-4330-a30c-d18cffdd5cc4	Full Scope Disabled	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	scope	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
6873c7ac-5576-4254-9688-181a24f40d09	Max Clients Limit	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	max-clients	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
ac251b05-6c0d-462e-b6ed-57af5eacf535	Allowed Protocol Mapper Types	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	allowed-protocol-mappers	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
6eadee5b-ac90-45cc-a3a0-3dabd510cc64	Allowed Client Scopes	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	allowed-client-templates	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	anonymous
4c8bebb2-450b-48c2-8d69-c45af43ee04f	Allowed Protocol Mapper Types	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	allowed-protocol-mappers	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	authenticated
b1a5b16d-2721-4c0c-8ee4-505fc3704faa	Allowed Client Scopes	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	allowed-client-templates	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	authenticated
d7ec7a09-5df4-431a-9318-1f9ba62dc642	rsa-generated	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	rsa-generated	org.keycloak.keys.KeyProvider	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N
d1e830e8-e122-4cf3-91aa-c7027197209f	rsa-enc-generated	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	rsa-enc-generated	org.keycloak.keys.KeyProvider	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N
8ea16076-b27f-44b7-a286-59c8d66aad3c	hmac-generated	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	hmac-generated	org.keycloak.keys.KeyProvider	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N
2c258002-fe5e-41f5-ae84-26ef619dd6f5	aes-generated	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aes-generated	org.keycloak.keys.KeyProvider	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N
9a9fc9ad-5b4b-445f-80d3-bb7baa723290	rsa-generated	192c7eba-98c5-4d87-9f5f-059ac8515a9f	rsa-generated	org.keycloak.keys.KeyProvider	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N
b0e03d65-4a1f-4a4c-9d54-56d558899e2a	rsa-enc-generated	192c7eba-98c5-4d87-9f5f-059ac8515a9f	rsa-enc-generated	org.keycloak.keys.KeyProvider	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N
db5b95a6-b3ce-435f-ab01-2ae3471354e1	hmac-generated	192c7eba-98c5-4d87-9f5f-059ac8515a9f	hmac-generated	org.keycloak.keys.KeyProvider	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N
311ae904-72ea-4016-9aa2-269f4b5ae90f	aes-generated	192c7eba-98c5-4d87-9f5f-059ac8515a9f	aes-generated	org.keycloak.keys.KeyProvider	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N
39c53378-aa55-4228-a36c-634001a263a6	Trusted Hosts	192c7eba-98c5-4d87-9f5f-059ac8515a9f	trusted-hosts	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
4e2cefd3-04eb-4a44-9a29-f7595dd753e6	Consent Required	192c7eba-98c5-4d87-9f5f-059ac8515a9f	consent-required	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
b2b7be5b-301f-40e2-8958-ad5e8f0d9bea	Full Scope Disabled	192c7eba-98c5-4d87-9f5f-059ac8515a9f	scope	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
116b0f7d-656d-474b-bbcb-1be3cec8955b	Max Clients Limit	192c7eba-98c5-4d87-9f5f-059ac8515a9f	max-clients	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
19c8f4a7-f9a9-4574-8945-370812594a50	Allowed Protocol Mapper Types	192c7eba-98c5-4d87-9f5f-059ac8515a9f	allowed-protocol-mappers	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
09da26ed-2d42-4a37-9cb1-8063ff044e96	Allowed Client Scopes	192c7eba-98c5-4d87-9f5f-059ac8515a9f	allowed-client-templates	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	anonymous
4abc05e2-ba8f-4c68-8eab-059821c194a7	Allowed Protocol Mapper Types	192c7eba-98c5-4d87-9f5f-059ac8515a9f	allowed-protocol-mappers	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	authenticated
47244a6e-e012-414c-a9da-26a574d69613	Allowed Client Scopes	192c7eba-98c5-4d87-9f5f-059ac8515a9f	allowed-client-templates	org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy	192c7eba-98c5-4d87-9f5f-059ac8515a9f	authenticated
\.


--
-- Data for Name: component_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.component_config (id, component_id, name, value) FROM stdin;
843c0197-1248-46d1-89ed-d57bf9ce2c87	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	saml-user-property-mapper
acd44c63-92a1-4216-80d6-6adba1d43504	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	oidc-usermodel-property-mapper
c4d0e515-2f2c-4711-9d4a-aaac814dfccc	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	oidc-full-name-mapper
4cfe92d4-6872-4c86-bef8-ef16de43f00a	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	saml-user-attribute-mapper
1b6108aa-3164-438b-aea9-3315d43943f9	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	oidc-usermodel-attribute-mapper
939827f1-e497-4654-b554-2b96ff404672	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	saml-role-list-mapper
2c10c3fa-f0a9-4165-aa6a-8586ec0afa9c	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	oidc-address-mapper
2768ce53-ed7f-4a07-962f-719700c7517f	4c8bebb2-450b-48c2-8d69-c45af43ee04f	allowed-protocol-mapper-types	oidc-sha256-pairwise-sub-mapper
cc7b575e-2aad-4882-83e8-ca20e1eb176b	b1a5b16d-2721-4c0c-8ee4-505fc3704faa	allow-default-scopes	true
fcab8fb3-3eb9-438d-b074-aaa3834456b3	6eadee5b-ac90-45cc-a3a0-3dabd510cc64	allow-default-scopes	true
e6bd1337-dbbc-457b-a039-025f9cbe7a82	6873c7ac-5576-4254-9688-181a24f40d09	max-clients	200
6650e48a-e5ff-41a3-8d76-e415cd9bc4ee	eac942d9-7640-4467-a5b3-ad255f48238a	host-sending-registration-request-must-match	true
913d40ff-2cfd-47e8-a6c2-ac1e026216c2	eac942d9-7640-4467-a5b3-ad255f48238a	client-uris-must-match	true
d910ceaf-a692-4c47-81dc-ab33ef3dbf46	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	oidc-address-mapper
e38a0b1e-c387-4edc-b30f-6552c0e0c742	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	saml-user-attribute-mapper
c4cea11a-14f6-47ed-a107-b0c23aa63951	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	oidc-usermodel-attribute-mapper
92b8037f-173f-446b-8340-28b9444e413b	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	saml-role-list-mapper
054c7c9f-4624-4aa5-9ffe-20ffb2502b1a	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	oidc-usermodel-property-mapper
c49969bc-91ce-4a0b-8d3b-3438e59302cd	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	oidc-sha256-pairwise-sub-mapper
9593fb6c-7b38-48eb-9186-6d1222ddff73	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	saml-user-property-mapper
1cef2258-0774-430c-9605-b956dba29907	ac251b05-6c0d-462e-b6ed-57af5eacf535	allowed-protocol-mapper-types	oidc-full-name-mapper
5f120c94-fef2-41ee-8d77-ec6bb3f9e929	8ea16076-b27f-44b7-a286-59c8d66aad3c	kid	49ce39a3-044f-416b-9d75-27e9264b6124
2ae18d17-e5ba-4dc6-b681-046eac6de4ef	8ea16076-b27f-44b7-a286-59c8d66aad3c	priority	100
df3d05da-f0a9-47c1-9ca9-6f5c6bbfbe6b	8ea16076-b27f-44b7-a286-59c8d66aad3c	secret	0w_dKCVoMDaiyZak_tLE60vuFK-_bVVHUXIX0Bs1HqCm2QEdJdoZNLcUn12b3g_S4U1csWhVP1ROODON1uRSgg
879607ef-498f-4349-8d5a-9adb292c82eb	8ea16076-b27f-44b7-a286-59c8d66aad3c	algorithm	HS256
b194e985-6a5d-49bf-a416-7f27d3961c96	2c258002-fe5e-41f5-ae84-26ef619dd6f5	secret	j13dpThfpcM3AiReYAVmRA
e031cd4f-0e33-4f72-9241-dd4f59316d7c	2c258002-fe5e-41f5-ae84-26ef619dd6f5	kid	0d4e8201-5150-4603-a4d0-4fde01068f08
1df552de-7394-4ae6-9cdf-e22b922dd3fd	2c258002-fe5e-41f5-ae84-26ef619dd6f5	priority	100
cf8a3827-242e-4cfb-841d-3ff99e691bb1	d7ec7a09-5df4-431a-9318-1f9ba62dc642	certificate	MIICmzCCAYMCBgGL126R8zANBgkqhkiG9w0BAQsFADARMQ8wDQYDVQQDDAZtYXN0ZXIwHhcNMjMxMTE2MDkxODQ5WhcNMzMxMTE2MDkyMDI5WjARMQ8wDQYDVQQDDAZtYXN0ZXIwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCUPac8BEMtsOvgKMbOc9HOucB14pvYsj2nn57zhZrtp4bS1uVE3VsRP3C1Z2JiAtKUxyYlVIPLI4yZQ3fvOWcYAq+fjl3P9G8SgcCv1jnBD+9KidUKvYgRorb/ao2Rp1dT4yS2QI+FVHyUbdLw5P6oumiVUDBQZOgicKr5+2eivq4+RlPG/1Gkvc6SvklFJMnphUd078EMYAlHL0ni2hpmL27+cv6fMmfIc5mwr/gffIMyEh94doJj7M6ikRvjFlCgs4PaavF300Tg0eTxTbj2m0gQapOdC8t10UTIGCXT+3vVgWVyFhYlMf6WKjPcLY9YCNiggHKzRH0lv4NY8EKHAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAAroECxg7IoM4hKJL6fm0LPlmLR5WYY8VGiUQRqx8koe5F+6nzwJBMNQjU5a8kl5n0XFzy31ny8E/v5DvGMUggUGP/Z3vtzsdjz9fOn0unynwaTndplCvLUGoojOYjyObzJg2n3jKRIwBTjZVIt3OSSB+1c0ztDo/dO60ZxEtd0XS0xuGG6R4E+tdJjREL+1rW79A80iKyLTbHLl66nH4Qo2Cq4YcdeB3AfsEwCTeWSFDN/AViovSQtAJCcxJuBXwsxSzJSyyRLq5lPtFvn4/ZyzDy9Tin3GuIpAF5CerhEy5lxfsqUK2mWcwZAB2fJDB6WRbf27F8S5oL0uZ7gQktM=
48573056-a203-4443-acac-452e1c8db7b0	d7ec7a09-5df4-431a-9318-1f9ba62dc642	keyUse	SIG
797667ad-4ab6-4a21-ba52-cea0f88555fd	d7ec7a09-5df4-431a-9318-1f9ba62dc642	priority	100
f8685c1c-8018-464a-8d0f-dd1e5175b15a	d7ec7a09-5df4-431a-9318-1f9ba62dc642	privateKey	MIIEpAIBAAKCAQEAlD2nPARDLbDr4CjGznPRzrnAdeKb2LI9p5+e84Wa7aeG0tblRN1bET9wtWdiYgLSlMcmJVSDyyOMmUN37zlnGAKvn45dz/RvEoHAr9Y5wQ/vSonVCr2IEaK2/2qNkadXU+MktkCPhVR8lG3S8OT+qLpolVAwUGToInCq+ftnor6uPkZTxv9RpL3Okr5JRSTJ6YVHdO/BDGAJRy9J4toaZi9u/nL+nzJnyHOZsK/4H3yDMhIfeHaCY+zOopEb4xZQoLOD2mrxd9NE4NHk8U249ptIEGqTnQvLddFEyBgl0/t71YFlchYWJTH+lioz3C2PWAjYoIBys0R9Jb+DWPBChwIDAQABAoIBAESMUeW1zt60/g20rWHQOseOK4oXlJtaqJn3fMf9EwwsOHMMfg4fEbpjDJpFyT+rMHcts9z1PNBVivFgOnh7ocl/jHiKm6TK0gXLzC9DL4ev96YPIF2MEPyesmJfgkFFEWOwGEzSg8tSqxzzv+Q27+9T64KIBx9V2eX7FYTtFRoywCjE7Qlk+zwAnm3joSJuCBBKKOXwlvHEp5owJjbAIlQhHn0YPTK06reenz0GKaEws2qURXQoMP+2qgSX0I2JHhCnceYD1Ov7GpG+OHmjqe/dv5n4mPCC1AURKMzrq1CC6GjJ6mpJu+9WLhC4UtRLTg+4MuHr5C6zjC7CWZUufRkCgYEAxyWTfGQ65CYibOTXg3dC7/Q30EZ7xY+fWtmDUa7Xvked/jhbqzNFwfno8u4hIOTAMyncPpOzV9cA9OnndVSfSA8KgSAsiLp9NssR/izzLpEGE+qDROkvHnTob+b0lf5t9dvarZTcjQlK0G/Jm+4urcCltpif6tHm1sJCZHvVsyMCgYEAvo+r+aeHhlSIDNZWwqT2HNeomn/ZPAgA+vA0MJLnqkxf9488VOimaXh3uMxcsO8lH5viC7OgZSsLJGCzZ/u3+O9Ha8jaCXzbRm5FsLitmXq/ELjJQI1cSXWtVlgrAIe1KvtYr/j3BLp4HBtkcN0KW7lx9imCHwaLmuXCxn2Lq00CgYEAi0v0UtEFBGrML6EOQi3ci10m4S88Ch+A1ppIqY0D6VvM3nJrZF/Tzm/RCoOYdpqq+d6w6LCFhM6mI6mstbxAQbYLofBwVh8j0HzQlBq66vqT5sBlm4ED7WjW4NcKhBRYs91Zo4r5jklOpGdc/Q3oZq7W+tbdHPI/Zj6xE/ouq0MCgYEAsCjQqjGcryllu7hI7BbjDTavvmOBxmT/wvpaxKyJTHzeGlRnSXbon4el5UfGSCpK/zVzea3MELoBytc6Al5Ia++G7rT2Gt85NZqrAfs3QDKgfizUnsAPGDmYy8Elv4+0gs9n5QUaFVzru8/2wf8UnEaKey1UBKpgVAkiTauxeeECgYB2tFe+1MoT793EfgFSfEFQGKEzlH6zauogO2vR8m9FK6gRapH0FHsyxnnyXUFHqfRn3/BCfWR8PlG/HaiE3pU2jp/0yFmDIz6l/QA9rVCLs7mHeWpuJnJtZ13xTCTU/Ri/098eS0TfA8E2PMktcJXQWlt/Ns5vML7VVFpBviaydQ==
138c66c2-0b18-4f8d-85b2-b0fb012c5bb0	d1e830e8-e122-4cf3-91aa-c7027197209f	privateKey	MIIEowIBAAKCAQEArQ5YPBXrOMhh22bdT84bIIUK4lICTGS3kYNWYIYUI1R33Ut//B6wob9Od9qny2WcXcKEV15r5NAi9aGiFtz6e5688sw3NUw1VX1GIZC/JdyAFfc9hgeETPAkrHRZagvYmsc2G8Dn81dkEHRN7UhXs6H65gfFdu/Uhc9NNIUUjJ8mSR4Kcos43kdPugz3hQnkAoKPdXFq0CcIy6GTgV+ixhzb8fU+17x1F9q67NaEohzi9ZUW96kglE+8kk3xpfx7to8Q1lpNAA+92z73dXrOUWQMh+oosEIsuDJP4Z88OoaaYZuFz1AzzGgnsduVSurfz1u5M9mYDsCteRCgPKsHDwIDAQABAoIBAD8lnti9/skHhX2zuUnnoUpqgaA34JLTpZA5ZoluI2cI6XwckqUC5dz/m7hsVxIHD9m+ot/mmmQx9q++vRCurc/yCmxmTDbsigGZ5r9UvAsqvKpHP3HqyEHy1s7+3amujOldi8bwyzKmTuMaLV1KKoZnss/BQjK2LMxu6nMhpG/zARr1XGcjU60JUvsj+gHeny49eaEEB+8trShi6Buz4ns3q9PmpBSJJiqH9///Hn5pdVB/3vflJssqUTRp1BeiUfsnrqspD59YadZwR4IQPNu2jD+ACfb3qYqTdu7BhyEZDpIYPp+P+98t/eMNRRvXhwIEIEVCr+WOALShvLLwyVECgYEA28P81aQbOZOQRXR7GqdwBCMo54fMWTY6JlxO+kFjudQ9/aF6PUCG3sTDni4l1tqd4KgVgPwbVRDrypjQB/9nPeIPN6ZINyq/GU3WwEeMNXRmmrX34krLs8bLOULiwkjUGryIdqqtnjeZTAHUs8DVNqm0m4OeKnE0oznYsBCpvoUCgYEAyZbPNm2fxpgaBMOvpzwvF2EnAE3CFzKgQRwD9Edp08Iq12zHkZp+Scl8hqkpO8wUEZcHey4EHvdbVZvwtT6h/BBjDcMIOnCqfPTAjdJ+Dlc58yhgLbMkd2uZungFnUOWtj/hvn5WMwSyzLB8SsIFs342y7dEC0bF7hX/2dr5NYMCgYA8p5MYw/pfocKn6MYxTRU1jx6zCF/2H2ldPQzvNSz5FQMnBXJfhXez9EqpVcNL0XrRjpKgzvQcPldVy2dfTbaI9eONUG+OClZD/Z/P4e9osX/AI4kPA+XE8JEWdMdxJ/iiiHaBignxKRc+SyMRmZ8/PweCBIma3TPR+R09OtweoQKBgQDC1Mq4JANEAUVETYy66OPqiK8VEBICMZ/IzbbUpSCW1RZq1mubQeHElsOPsnZzoK3Uwk8ssjCxbQgNGYXu5fXQlFXnuxN8x98+nZ5sc3/5hDwx0lgCUx1vfcM6AT4L3IMQ6XTYk2nkLSpRwlCeQB8ad2WmRh2xeFlb3k9E0uoA2QKBgA4hw009QL3/97Sw1Zognl25B3VRdSy/f0a1S6NYLTBMJxmfBE1d4ciTrh36T4ePBQOxfWw+kxEg1adEAkJScZvWTFyzsIXg8cCJIGDWWapXDlzk3kWyEHNYjPRb2lHKIdqb/Cxue7oNV8FmKUhVVf4oKKO0vGd50/x5JFJWjdoL
008c4abd-d1e5-4e5b-b573-b40cb331e2c1	d1e830e8-e122-4cf3-91aa-c7027197209f	certificate	MIICmzCCAYMCBgGL126USTANBgkqhkiG9w0BAQsFADARMQ8wDQYDVQQDDAZtYXN0ZXIwHhcNMjMxMTE2MDkxODUwWhcNMzMxMTE2MDkyMDMwWjARMQ8wDQYDVQQDDAZtYXN0ZXIwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCtDlg8Fes4yGHbZt1PzhsghQriUgJMZLeRg1ZghhQjVHfdS3/8HrChv0532qfLZZxdwoRXXmvk0CL1oaIW3Pp7nrzyzDc1TDVVfUYhkL8l3IAV9z2GB4RM8CSsdFlqC9iaxzYbwOfzV2QQdE3tSFezofrmB8V279SFz000hRSMnyZJHgpyizjeR0+6DPeFCeQCgo91cWrQJwjLoZOBX6LGHNvx9T7XvHUX2rrs1oSiHOL1lRb3qSCUT7ySTfGl/Hu2jxDWWk0AD73bPvd1es5RZAyH6iiwQiy4Mk/hnzw6hpphm4XPUDPMaCex25VK6t/PW7kz2ZgOwK15EKA8qwcPAgMBAAEwDQYJKoZIhvcNAQELBQADggEBAAh4G7bRbHfcY3OgD6TR639g31HzZk6l1sbU7p3/Ewx3b+IoOXw7EYUHJ5/Qa5ioU7fbzaYRRghZoe1NgXLnUHaA9rmIiHB6QRhmWZ4/AWoxu7/WQJhWN/utTk20rz9b+T/4lc81aZNm6sYYwqZRLTMf/0i1DR93XDXrioCK3FBl+OZ0S47hhLtpc7rnTqNT3HT5kqug7vMHMqDDqKYhZ8LxWti2j4JsSaYcWuxM9YENbZOVVHG6cWbSphgnHznH4EESyawIutqUaBPe0zs/o+4AfPNIjg8W2EsKk5lOraT/Ty2lra7SEjSOmUpSHtAtfF0RjtWsU0u2pHnJ2wmvYI0=
490440d8-21bb-4f96-b6de-41817ff0c6cf	d1e830e8-e122-4cf3-91aa-c7027197209f	priority	100
563d912d-4683-412e-804f-bce2649c7111	d1e830e8-e122-4cf3-91aa-c7027197209f	algorithm	RSA-OAEP
57303a39-9764-4b63-9324-68e8b1e4fcf8	d1e830e8-e122-4cf3-91aa-c7027197209f	keyUse	ENC
5171f17c-776d-4803-b7f8-4a2b8959e82f	b0e03d65-4a1f-4a4c-9d54-56d558899e2a	privateKey	MIIEowIBAAKCAQEAwfxxg+0ZBJjdk6aWvHd96JpW+r5rkBVS1rBvuliA+NfoZ2qucDg5UUxK3nDeaFAlv+beiBFYDdv8xTVaozGnVvg5UiJRZo4ZTCfCzv76aPG950q8Pn8SNkwY9JBUaTzznHcvhEOFl5SVomCH682PD+gtX6B1amnEVsVL7rVnJziwT05P4Y3HW6rNHj5Sm9xToZWijzYGOZl716QJJ+OkzpsbFDJ4jG9RFObcz47aqkUV9R8IJt3lRs25v0CKNpg68/tFsOj3jRqPE5sJ97mTPSBJnmg6P2lye3hTkUFOOCURQeCqW1rmJeLuBVX7kw6Pkk9IwjNOW0guAdjNW8x80wIDAQABAoIBAD8e8pz38HUTfL4HrfLDev/OANF0VrG6jor3PFPJaqYOMzw7dWlkkhoHFjGNToFo2u+3ot9prVpNI9HTy5tgk8/z00sLiasyP78NDRGn3Dl7t8xkAB7h4D40wsYJlL3trGNUUOzbv8OUAKCmgnPTHmMRrHn6T1qB8fY+Grgg5ODYuyHR28hJgrpg6XBUQm9rRAdjlXMyvp/kNDxbh5vE5/lEasSSctgbT+qnZNl90O9g5HCfVFNajAhv5aqfYufxmSu4M/w12BzxAR1TRT+gniAYhgJ7mp5A1jgDvmyX9X3+5lcbiJN8qqGmnEdlFeW5WouHA5M1XP2g1JU4njvAHKkCgYEA6yd2UqdiaHW44S84F/Rylyw+lBjX8NIILIQ2S2tHrdoltiqfVZFY5OxALzhMR+mV8A2ZXVSYPwAghit8kWY6AAzbukLDPISFg608c9e9bT054LZcu/SkZguopUohO3xPqoGm84XTss3emeMD/5zh0vW4LwWmIn/jsk5v40sNFs8CgYEA0y649joLvPfiY8YLP/nULSaIr5FjQn+gh8DRdurhkilVpDBypZ8FkVBPk/lnA62uzVbwv+3useWVXvS2+fyG/BED3YmRcd4VjdbAtLO9gsyexsuGwZqkue4pOwE3pjxjGcbXb4OUydfBguqQ69qGYnIlnnUsHGtIaejErDZ8er0CgYEAz8JHyfLVARGxTFLZrmBstZ+Dknj4oG4QhrQw/CVGaRVpaC70IzeNYIRSmOWWj5qSvEpni4voDxFfqurU3emBqPWzVDcUI226QIJX/MlJNTB46E52VCFq9jWqxI5gGhxUjoKKLHG6filhWHi32aiT5Dzwg6rsA2MWmzytohV29QUCgYAoh9UT3LwX/nNCtuW915LzP2wIVhz4zEnhBA6vhhDY3noDUxEN3GFTLFi5i6pLuG/OFRuLmnyvQ+LRIKJlhCPcCN/3CsoRUpBMcqT1iXGbwu3ONY2dZrKqxJzBKFCn5PsYHWOHkXdi7bfECoTZ30zfZAz4RoC6y5RQT04/xw1I+QKBgHJQ2siJ3orB22kQ0iK0nwVAN//D7InAIQZEeYJ4Pt18gIZvVS0n6n5w710W0I0/JFj/pwAMNzKgYip2Dtg5gnnpPR0TBiNEpRYxKvkfo/RvKNL7GuhQQCeugDNSktnrLMTw3kNR2bwJ3EJu4K/j6iK48arPa33AV9o2QUKKGkfk
eef3af5e-47e1-4eb0-af41-d3b29a834406	b0e03d65-4a1f-4a4c-9d54-56d558899e2a	algorithm	RSA-OAEP
98ef8ade-98b9-433e-aff3-8ef2a1c6f815	b0e03d65-4a1f-4a4c-9d54-56d558899e2a	keyUse	ENC
121f3be5-d41d-4f89-9b17-dbce1780dd16	b0e03d65-4a1f-4a4c-9d54-56d558899e2a	certificate	MIICnTCCAYUCBgGL128V/DANBgkqhkiG9w0BAQsFADASMRAwDgYDVQQDDAdsb2dwcmVwMB4XDTIzMTExNjA5MTkyM1oXDTMzMTExNjA5MjEwM1owEjEQMA4GA1UEAwwHbG9ncHJlcDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMH8cYPtGQSY3ZOmlrx3feiaVvq+a5AVUtawb7pYgPjX6GdqrnA4OVFMSt5w3mhQJb/m3ogRWA3b/MU1WqMxp1b4OVIiUWaOGUwnws7++mjxvedKvD5/EjZMGPSQVGk885x3L4RDhZeUlaJgh+vNjw/oLV+gdWppxFbFS+61Zyc4sE9OT+GNx1uqzR4+UpvcU6GVoo82BjmZe9ekCSfjpM6bGxQyeIxvURTm3M+O2qpFFfUfCCbd5UbNub9AijaYOvP7RbDo940ajxObCfe5kz0gSZ5oOj9pcnt4U5FBTjglEUHgqlta5iXi7gVV+5MOj5JPSMIzTltILgHYzVvMfNMCAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAhbgg51y4naME7qt4iXlZOiBU7MmmvpfbmWnUsHDf/5m0KT79aXbdEg1+Gv2e9jmdFC67KU+cesC3PSXW47T4grCSeXEiIIyht5jJAR7RLbzCw3WtWLjUf/OqfjbSlDtmusmuwAjMFmXCwSTvWaT7I13GKiulvZoRee7Jf0V7NSmUA0QoXQkfgacXl279dNH1lbyMEUAX02JpDmicPQ8SHt01zSvCEyhu+XZ9buzDXehL+tiTNbGuFgw4ejkkAAPZV+znTvlZAJEtTNsqf7EGg3qpxohxCZYroaUGiyNQdnvoedsnPVPwpS0TD70DpXxrp6S1EblqtbMPn0C1T7cZbg==
e760783e-4cfc-4df7-8720-09423a78cac2	b0e03d65-4a1f-4a4c-9d54-56d558899e2a	priority	100
e5565aa2-b696-4a80-a3df-3f5159e3f514	311ae904-72ea-4016-9aa2-269f4b5ae90f	secret	KhjOdrflpm_GymTt_uQXKg
fc062c1e-0155-4bfa-a552-e0ce8dd6f7d9	311ae904-72ea-4016-9aa2-269f4b5ae90f	kid	5925594e-af14-4948-8283-ded69ae5b8bf
04ef028d-29b4-4db5-a159-e961555dfc04	311ae904-72ea-4016-9aa2-269f4b5ae90f	priority	100
05ccea92-757b-48fd-ab83-f6d52d94613e	9a9fc9ad-5b4b-445f-80d3-bb7baa723290	priority	100
9acaddb2-8f60-4698-a039-4dec28711fb3	9a9fc9ad-5b4b-445f-80d3-bb7baa723290	privateKey	MIIEowIBAAKCAQEAyuLBkzRxZFteF2Sfx7vt/Qpng6WPy4m4z1al4g5cbiAgV2vO7px7Ppk6jIs/45hxslS1kn7yBI+vMaXon5mAn/eVKZpqLq6Ptr91ZoMDB9TR4bywU6YZ+ttpFUndw4iHrO3pyAx/lUjp9Nl8UyyWbCLWUl6QzYt2CEYddb5JApBO99FlXc9SfPuETlZ3PLuxsw/fo4JmtgXip2P5RVZa4kZgflgacp3stCe0Bs1JyT+zGEbQtzQaJRSVeEZg993RbuVjI8pidMOVcYidNMJjRvSzowDpokWSXxOcvl0v5XQ98kXFMLRfXeuDFysX/Sm1NAUXEw/7fxFwmKYpQH7/awIDAQABAoIBAGKEDzj6myD/GMZFLyzefWaEudT7/MH5wwqy6WPGU22KHgo1KEtHIrU31G1QZJqQeIz+gxh6mexLFOgHxthQwltq7jxAZdT7IH+9ojU/4qXX2n5BkGFd43mjNviGYK/EyRTYhc+E+iK0QB6LyMneecBSfj2K+8dDM/I6ka2N04fxSzzrH+wqccS+LBRT6L6sLEsR0xhX7YYU5ofAdaMyKrvPOYaCIGs59GmK7I80KVlusEjy52siLAHtuTpeoQ6LhfPLSpe0XUPV6tRC2a+2pYs2KiEPa7I01ntkaTB6Buy4NTksYz9iUN4u7MUmoNcqVVRNWnjF/xLl9wnnFWlCm+ECgYEA74bepZpKzFDu6fEm6pd6KVLNizfK88Rm4305iNoBUEODIeMUH7ywo4x4DPXkL30e5uEAXvYnoJmvROa36RLtuh9Q8u6+Sk2qoqUEspRZzY6pH1MsCkKi5vFzBYbYYMtnn4wUcmRexjyGORcNI2kUY5PIoot2cf5N2sVlzkCCMPsCgYEA2NbH1T1+UHUcHTxjb5FrPmOKUZJYmPAa9R6z0/Ti+JnGggeSRunPlqCoFPgMGZGPUsVlUPC3NcTRzTFzN9vTqnVOevJXtn2tzGasr7pyJc5W6UrGcVPvNyzk5E7k9B3UQmxj2waIIbS1SK44iNL3OGzqMamuNnPUASwJmiNwgFECgYEAqO0pYQmr7uS1WnAkzhX+pd4r8B9tFvZQyeerCAUYIA89EE0iCC//M5kBocJZJ9TKUnIk3NQlpnI81g8RbWNYHYewg2Q0+BpGWWagJYHSw9H1HI5/5MySLuXiBOfQ+pL5heA5G2QGIzDUSLclIPAe3QuA2IIbCtIa/ktxPUDpkLkCgYB5IFlWi9hAl3qR9kbRbtkKa847TNXC8PUOEg2ADB6xoizaO+KBTGCSksHxnLIdokr+gJfdA+pD1eMgjUwAWwK9CHRDh5ZpsYDhWkWCkFLtPXsdLJD3g1xwZNqjklKg7vy/8g5Brj9jHK/bnr6j570Dvwt/nHpdnoxB71iZyswwUQKBgHYM1PGVIfOj89yGCj5DQWTEMIprzfCIXyEK/+DbEBaEcgy0xEav9qw5Qtu0rNvvNYDVv9zYkv1Zxg5as9qcrvqOxvp4P2mBTHW9dkVqiFbgVAg44PAEjLmsfc2aVBIQxsv8ljU25tWb8XmsMcfr2JDpkCxutjKJ3JCo7YWhzbSV
43144a83-ea2f-4b46-be69-8fd36948a913	9a9fc9ad-5b4b-445f-80d3-bb7baa723290	certificate	MIICnTCCAYUCBgGL128U/TANBgkqhkiG9w0BAQsFADASMRAwDgYDVQQDDAdsb2dwcmVwMB4XDTIzMTExNjA5MTkyM1oXDTMzMTExNjA5MjEwM1owEjEQMA4GA1UEAwwHbG9ncHJlcDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMriwZM0cWRbXhdkn8e77f0KZ4Olj8uJuM9WpeIOXG4gIFdrzu6cez6ZOoyLP+OYcbJUtZJ+8gSPrzGl6J+ZgJ/3lSmaai6uj7a/dWaDAwfU0eG8sFOmGfrbaRVJ3cOIh6zt6cgMf5VI6fTZfFMslmwi1lJekM2LdghGHXW+SQKQTvfRZV3PUnz7hE5Wdzy7sbMP36OCZrYF4qdj+UVWWuJGYH5YGnKd7LQntAbNSck/sxhG0Lc0GiUUlXhGYPfd0W7lYyPKYnTDlXGInTTCY0b0s6MA6aJFkl8TnL5dL+V0PfJFxTC0X13rgxcrF/0ptTQFFxMP+38RcJimKUB+/2sCAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAFxjCw6l1ly7mNvzxl6/BKK0OJ0AOcEISfQWzyHaMUmZe5lkhDic0OR2D5DbkotgcmiL8G4Ti9fJADT4WAajSRU+dOQa8BmDCsYtZJpHVmmwcpZAdBqwC/Z22nh92X8saUskST5RvYx07y03v7SQOOxe5nGjHnAb/zh3siUtD1JHs/eUP6i/nUEDDgTgGF915fN42ymmBmHMUMLZJc5JhV1f9MGHnnAu40FM2SUrPyYc19e7vAGezHTXerhkAPxp+0+wKWfHGD0sTq8UmNjTL02KjWgf1Bw828Ly+oAbGMPDgmmtmhKn2KdRJ67TCgYYWH5itHAnbGfoDIYEqWRB0Rw==
57bffa1b-2460-404e-8281-81e8f3bb96de	9a9fc9ad-5b4b-445f-80d3-bb7baa723290	keyUse	SIG
e192ef6d-d6bc-40ed-acae-8bbf7c1ddaa3	db5b95a6-b3ce-435f-ab01-2ae3471354e1	secret	Euh3iCSsIpEMV_Bl5NFaiOfqQ-8ZwKSQGUo-97qtCMpns1zf6BcraKgkf6-9VUUSD9xwyJpSfVjjv9sFuE_OTw
703371f3-6967-49c3-8c54-13e5a4b6fdcb	db5b95a6-b3ce-435f-ab01-2ae3471354e1	priority	100
4522c46a-3d2f-443d-a226-231cc6497e91	db5b95a6-b3ce-435f-ab01-2ae3471354e1	algorithm	HS256
b7bf163d-70c6-4de6-aa65-c443d61d9074	db5b95a6-b3ce-435f-ab01-2ae3471354e1	kid	7d0bb5f1-3a76-4bfb-9abf-84d03fdbe062
e0a3471f-f010-4019-87db-993c1d3b1377	47244a6e-e012-414c-a9da-26a574d69613	allow-default-scopes	true
d887082b-baa4-4a0b-a480-d91d290db22e	39c53378-aa55-4228-a36c-634001a263a6	client-uris-must-match	true
d7a73c15-9667-443a-8488-73a9a2fbe787	39c53378-aa55-4228-a36c-634001a263a6	host-sending-registration-request-must-match	true
86a3d105-997e-4b85-aa92-82d8e5ee9b33	116b0f7d-656d-474b-bbcb-1be3cec8955b	max-clients	200
468ebff9-413a-4dc5-96d8-bf8c5ba8c7a3	09da26ed-2d42-4a37-9cb1-8063ff044e96	allow-default-scopes	true
b1f41ba2-cbb0-43a8-9a6a-7b83eaad539a	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	oidc-address-mapper
eb92f6bb-7584-477b-956d-ff71d62617e2	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	oidc-full-name-mapper
9055f285-6cbc-43fe-a42e-285036239f60	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	oidc-sha256-pairwise-sub-mapper
48bf439f-3c33-4538-bab9-631b9246cfc8	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	saml-role-list-mapper
1f5477c3-43e4-46f8-8d58-e2286177f418	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	saml-user-attribute-mapper
6073f620-dde6-4cc4-a127-44913ed4ca67	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	saml-user-property-mapper
af63afc2-47cd-4d01-b1e1-4ac2b9e43d18	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	oidc-usermodel-attribute-mapper
404525e8-f46f-432b-8ea3-fe756be48560	19c8f4a7-f9a9-4574-8945-370812594a50	allowed-protocol-mapper-types	oidc-usermodel-property-mapper
19df6039-984f-4e32-859b-43f6333b66ff	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	saml-user-property-mapper
66a719d0-834f-493b-a30c-956c22a33e65	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	oidc-address-mapper
775b5aa9-8e21-4cc5-a966-23da613bb5c7	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	oidc-sha256-pairwise-sub-mapper
07dd313a-1e48-4b5d-9737-626198d2bf2e	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	saml-user-attribute-mapper
caf8c616-a5c4-4db9-8603-3c7dbcd40987	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	oidc-usermodel-property-mapper
035c469e-7b05-4720-9e5a-f865566d6e61	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	saml-role-list-mapper
03d65df2-98de-4b57-95b5-27cf919a13b4	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	oidc-usermodel-attribute-mapper
8a8fd693-61d1-44d4-b3d0-d84eb8a85a6a	4abc05e2-ba8f-4c68-8eab-059821c194a7	allowed-protocol-mapper-types	oidc-full-name-mapper
\.


--
-- Data for Name: composite_role; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.composite_role (composite, child_role) FROM stdin;
db244a85-417d-4a00-a896-e9312fe77119	f878f2f8-582f-403d-90fa-b27afc636d22
db244a85-417d-4a00-a896-e9312fe77119	ee0717c8-8bca-4a22-acef-b11ebecfbe36
db244a85-417d-4a00-a896-e9312fe77119	cdc006d9-0d5f-450e-a789-b0302f9bcb76
db244a85-417d-4a00-a896-e9312fe77119	b3e7619b-0cc3-4203-95ef-04d93e17418d
db244a85-417d-4a00-a896-e9312fe77119	eac59232-b35c-4a86-9ac1-8a45661a8ffb
db244a85-417d-4a00-a896-e9312fe77119	e91628e6-caf5-4bd1-a456-5439d92697ec
db244a85-417d-4a00-a896-e9312fe77119	c589cc50-9f0d-4074-8503-f43030e973d3
db244a85-417d-4a00-a896-e9312fe77119	be042b2d-74cf-4ead-a59b-d0f570d99d82
db244a85-417d-4a00-a896-e9312fe77119	7e6afcd8-f918-40c3-b931-d37111136cf6
db244a85-417d-4a00-a896-e9312fe77119	5da77801-c20e-4b3d-8e75-7431f862db7c
db244a85-417d-4a00-a896-e9312fe77119	d80ba2ad-3b0d-4c03-afa7-bb5478aba1e1
db244a85-417d-4a00-a896-e9312fe77119	dc12ae77-f398-4558-a395-9c991984f44e
db244a85-417d-4a00-a896-e9312fe77119	9fdaa1fc-3bcd-4f74-9bf5-f887bfc53303
db244a85-417d-4a00-a896-e9312fe77119	cecf20d1-a0c4-4d7f-a34f-3a4dbfec6a33
db244a85-417d-4a00-a896-e9312fe77119	040c5a23-b2bf-47fa-a4b0-751797c519bc
db244a85-417d-4a00-a896-e9312fe77119	3a63f54b-72be-48c3-a72b-64abec570d55
db244a85-417d-4a00-a896-e9312fe77119	98bf02e9-40b4-4782-8615-9e91391b5643
db244a85-417d-4a00-a896-e9312fe77119	d140eaa3-71b1-4106-a950-7109e50a1c6c
9248d8ff-8fdf-483f-911c-b400a4715be0	249cb71e-51c3-4aa6-bbc7-160541653b0b
b3e7619b-0cc3-4203-95ef-04d93e17418d	040c5a23-b2bf-47fa-a4b0-751797c519bc
b3e7619b-0cc3-4203-95ef-04d93e17418d	d140eaa3-71b1-4106-a950-7109e50a1c6c
eac59232-b35c-4a86-9ac1-8a45661a8ffb	3a63f54b-72be-48c3-a72b-64abec570d55
9248d8ff-8fdf-483f-911c-b400a4715be0	407b7326-22e9-47de-b32c-f34bdbb48bf6
407b7326-22e9-47de-b32c-f34bdbb48bf6	10c09cfc-fe8e-435a-868f-905bab146edc
45b5847d-0e9f-4722-accd-bc48521a63ab	d9265bc5-9663-43c3-b1b7-72eea1c20ae7
db244a85-417d-4a00-a896-e9312fe77119	a4a196af-5eae-4719-9d55-8e4dabb27a99
9248d8ff-8fdf-483f-911c-b400a4715be0	c16af2bf-5d84-40f4-8b6f-09875cbde07a
9248d8ff-8fdf-483f-911c-b400a4715be0	4ad28e4c-c998-496c-8418-fbaac75767d9
db244a85-417d-4a00-a896-e9312fe77119	dd1dc591-25eb-41b0-ad9b-6626f578f3f9
db244a85-417d-4a00-a896-e9312fe77119	ef70fd57-bb4d-433d-87ce-b207be534105
db244a85-417d-4a00-a896-e9312fe77119	223a8341-34d4-4c4d-be7f-105ec6730c6d
db244a85-417d-4a00-a896-e9312fe77119	8eb82050-5e5c-4a00-b1f7-92a64f1bd403
db244a85-417d-4a00-a896-e9312fe77119	a2c38582-004b-4821-92cf-c9aced935469
db244a85-417d-4a00-a896-e9312fe77119	4b283bf4-f313-447b-bd3d-fc2c612fc7bd
db244a85-417d-4a00-a896-e9312fe77119	433a40d5-9dbe-4114-ba89-187ef4a67b68
db244a85-417d-4a00-a896-e9312fe77119	85379951-fff1-4821-8184-d027116bffb5
db244a85-417d-4a00-a896-e9312fe77119	b571f6a9-717c-4cf0-baed-e07c558d5976
db244a85-417d-4a00-a896-e9312fe77119	2e33949b-0165-455a-a342-71062e369bb0
db244a85-417d-4a00-a896-e9312fe77119	527489de-7576-4991-a629-3fb0c5604255
db244a85-417d-4a00-a896-e9312fe77119	febfa69b-d5f3-4c43-9274-081338c35dba
db244a85-417d-4a00-a896-e9312fe77119	14e594eb-c427-49c1-8201-593c2d6cbe17
db244a85-417d-4a00-a896-e9312fe77119	f64ea7a4-7f40-4516-a3ce-f388fe482394
db244a85-417d-4a00-a896-e9312fe77119	abd4c968-9e27-47cf-80ab-0e4e0af854f9
db244a85-417d-4a00-a896-e9312fe77119	164141e7-7f8e-41a4-a464-c13711bdc55a
db244a85-417d-4a00-a896-e9312fe77119	ad01d462-d24f-40af-a80b-46688d4100e6
223a8341-34d4-4c4d-be7f-105ec6730c6d	f64ea7a4-7f40-4516-a3ce-f388fe482394
223a8341-34d4-4c4d-be7f-105ec6730c6d	ad01d462-d24f-40af-a80b-46688d4100e6
8eb82050-5e5c-4a00-b1f7-92a64f1bd403	abd4c968-9e27-47cf-80ab-0e4e0af854f9
f9be7c14-1996-469a-8c08-b92068aff63d	7c8bbec1-20c7-4fbf-b002-69b81a7e16ab
f9be7c14-1996-469a-8c08-b92068aff63d	588cdf08-d847-4d93-bca5-a648ce7173ac
f9be7c14-1996-469a-8c08-b92068aff63d	ef1ea854-a8bf-4ae7-9ff8-b43034e18c7f
f9be7c14-1996-469a-8c08-b92068aff63d	74f4a81a-a120-477c-962d-3148529ff9b3
f9be7c14-1996-469a-8c08-b92068aff63d	21dc671d-d4f2-4698-887a-390353d575d7
f9be7c14-1996-469a-8c08-b92068aff63d	6f91aef4-6e10-454e-bb22-b05bdab44ede
f9be7c14-1996-469a-8c08-b92068aff63d	bc3af619-5c23-46da-b563-39303ffa4a10
f9be7c14-1996-469a-8c08-b92068aff63d	3fb93172-19ae-4ea9-a2b6-b594c1d7aaf1
f9be7c14-1996-469a-8c08-b92068aff63d	2635161f-d630-438f-a126-9d37f998be53
f9be7c14-1996-469a-8c08-b92068aff63d	b2b78255-c74f-4849-9ff0-ca0eac64459d
f9be7c14-1996-469a-8c08-b92068aff63d	c2976451-ff24-414a-a890-14458eca13ca
f9be7c14-1996-469a-8c08-b92068aff63d	1ea12752-aebb-4adb-a1e7-f63ff8d80d9d
f9be7c14-1996-469a-8c08-b92068aff63d	8b4b3d57-cf63-4cc3-a5f8-f20ec3b967b9
f9be7c14-1996-469a-8c08-b92068aff63d	c1720889-b5be-4348-93f1-513b3f449b8b
f9be7c14-1996-469a-8c08-b92068aff63d	c2572cfd-5df4-4375-8719-03f0530e921b
f9be7c14-1996-469a-8c08-b92068aff63d	326d4ec9-7301-406e-be3e-dfeb4e1d4c38
f9be7c14-1996-469a-8c08-b92068aff63d	bd29f472-7875-4521-878d-49f6b1acca06
355d504e-2e39-4d69-b225-04074afc8263	34d36fab-24e6-4bfe-a88d-21e87a12ecc3
74f4a81a-a120-477c-962d-3148529ff9b3	c2572cfd-5df4-4375-8719-03f0530e921b
ef1ea854-a8bf-4ae7-9ff8-b43034e18c7f	bd29f472-7875-4521-878d-49f6b1acca06
ef1ea854-a8bf-4ae7-9ff8-b43034e18c7f	c1720889-b5be-4348-93f1-513b3f449b8b
355d504e-2e39-4d69-b225-04074afc8263	0c0d6eb7-a699-4100-82b3-f0d6b94cfb10
0c0d6eb7-a699-4100-82b3-f0d6b94cfb10	670ae089-cd79-400c-852b-51d422e00d01
6dde7388-89d2-4ad3-8717-a816d9904233	c8001fee-9758-482c-a67c-8760461f710b
db244a85-417d-4a00-a896-e9312fe77119	758319a2-c266-48a2-9f70-e6672c75fd8e
f9be7c14-1996-469a-8c08-b92068aff63d	922ddad7-5850-4972-98ec-c4ea84623b24
355d504e-2e39-4d69-b225-04074afc8263	f70e4815-0644-49cc-8ea9-c6c87c4afb55
355d504e-2e39-4d69-b225-04074afc8263	d6cd7fe1-ed88-4175-ac9c-7dfc0729f732
\.


--
-- Data for Name: credential; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.credential (id, salt, type, user_id, created_date, user_label, secret_data, credential_data, priority) FROM stdin;
e7ff432a-dfbe-41b1-a2fa-dc6b9bfc0778	\N	password	74847ce5-bd87-4a81-93bb-9a838c80a99e	1700126430890	\N	{"value":"XckN9Buy8yfUhBiB1g5wDuvi25a+wU91Gmnd6YkBrg8=","salt":"Dhmk9vu6shXvjT1402Q/pw==","additionalParameters":{}}	{"hashIterations":27500,"algorithm":"pbkdf2-sha256","additionalParameters":{}}	10
0508d646-03b3-405b-8459-7b2469a2fa06	\N	password	773ef3df-7d55-4e68-a09e-e40c664adc67	1700563063556	My password	{"value":"E0R7E2duyGP+odUWmvsIQlbJ4qmi1QgwANA3IFr2j5c=","salt":"Nzp4oyja9ronHJxfdUqnHw==","additionalParameters":{}}	{"hashIterations":27500,"algorithm":"pbkdf2-sha256","additionalParameters":{}}	10
\.


--
-- Data for Name: databasechangelog; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.databasechangelog (id, author, filename, dateexecuted, orderexecuted, exectype, md5sum, description, comments, tag, liquibase, contexts, labels, deployment_id) FROM stdin;
1.0.0.Final-KEYCLOAK-5461	sthorger@redhat.com	META-INF/jpa-changelog-1.0.0.Final.xml	2023-11-16 09:20:23.796991	1	EXECUTED	9:6f1016664e21e16d26517a4418f5e3df	createTable tableName=APPLICATION_DEFAULT_ROLES; createTable tableName=CLIENT; createTable tableName=CLIENT_SESSION; createTable tableName=CLIENT_SESSION_ROLE; createTable tableName=COMPOSITE_ROLE; createTable tableName=CREDENTIAL; createTable tab...		\N	4.23.2	\N	\N	0126422430
1.0.0.Final-KEYCLOAK-5461	sthorger@redhat.com	META-INF/db2-jpa-changelog-1.0.0.Final.xml	2023-11-16 09:20:23.860217	2	MARK_RAN	9:828775b1596a07d1200ba1d49e5e3941	createTable tableName=APPLICATION_DEFAULT_ROLES; createTable tableName=CLIENT; createTable tableName=CLIENT_SESSION; createTable tableName=CLIENT_SESSION_ROLE; createTable tableName=COMPOSITE_ROLE; createTable tableName=CREDENTIAL; createTable tab...		\N	4.23.2	\N	\N	0126422430
1.1.0.Beta1	sthorger@redhat.com	META-INF/jpa-changelog-1.1.0.Beta1.xml	2023-11-16 09:20:23.945723	3	EXECUTED	9:5f090e44a7d595883c1fb61f4b41fd38	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION; createTable tableName=CLIENT_ATTRIBUTES; createTable tableName=CLIENT_SESSION_NOTE; createTable tableName=APP_NODE_REGISTRATIONS; addColumn table...		\N	4.23.2	\N	\N	0126422430
1.1.0.Final	sthorger@redhat.com	META-INF/jpa-changelog-1.1.0.Final.xml	2023-11-16 09:20:23.956943	4	EXECUTED	9:c07e577387a3d2c04d1adc9aaad8730e	renameColumn newColumnName=EVENT_TIME, oldColumnName=TIME, tableName=EVENT_ENTITY		\N	4.23.2	\N	\N	0126422430
1.2.0.Beta1	psilva@redhat.com	META-INF/jpa-changelog-1.2.0.Beta1.xml	2023-11-16 09:20:24.179783	5	EXECUTED	9:b68ce996c655922dbcd2fe6b6ae72686	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION; createTable tableName=PROTOCOL_MAPPER; createTable tableName=PROTOCOL_MAPPER_CONFIG; createTable tableName=...		\N	4.23.2	\N	\N	0126422430
1.2.0.Beta1	psilva@redhat.com	META-INF/db2-jpa-changelog-1.2.0.Beta1.xml	2023-11-16 09:20:24.20463	6	MARK_RAN	9:543b5c9989f024fe35c6f6c5a97de88e	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION; createTable tableName=PROTOCOL_MAPPER; createTable tableName=PROTOCOL_MAPPER_CONFIG; createTable tableName=...		\N	4.23.2	\N	\N	0126422430
1.2.0.RC1	bburke@redhat.com	META-INF/jpa-changelog-1.2.0.CR1.xml	2023-11-16 09:20:24.376847	7	EXECUTED	9:765afebbe21cf5bbca048e632df38336	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete tableName=USER_SESSION; createTable tableName=MIGRATION_MODEL; createTable tableName=IDENTITY_P...		\N	4.23.2	\N	\N	0126422430
1.2.0.RC1	bburke@redhat.com	META-INF/db2-jpa-changelog-1.2.0.CR1.xml	2023-11-16 09:20:24.400426	8	MARK_RAN	9:db4a145ba11a6fdaefb397f6dbf829a1	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete tableName=USER_SESSION; createTable tableName=MIGRATION_MODEL; createTable tableName=IDENTITY_P...		\N	4.23.2	\N	\N	0126422430
1.2.0.Final	keycloak	META-INF/jpa-changelog-1.2.0.Final.xml	2023-11-16 09:20:24.412164	9	EXECUTED	9:9d05c7be10cdb873f8bcb41bc3a8ab23	update tableName=CLIENT; update tableName=CLIENT; update tableName=CLIENT		\N	4.23.2	\N	\N	0126422430
1.3.0	bburke@redhat.com	META-INF/jpa-changelog-1.3.0.xml	2023-11-16 09:20:24.658141	10	EXECUTED	9:18593702353128d53111f9b1ff0b82b8	delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_PROT_MAPPER; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete tableName=USER_SESSION; createTable tableName=ADMI...		\N	4.23.2	\N	\N	0126422430
1.4.0	bburke@redhat.com	META-INF/jpa-changelog-1.4.0.xml	2023-11-16 09:20:24.774155	11	EXECUTED	9:6122efe5f090e41a85c0f1c9e52cbb62	delete tableName=CLIENT_SESSION_AUTH_STATUS; delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_PROT_MAPPER; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete table...		\N	4.23.2	\N	\N	0126422430
1.4.0	bburke@redhat.com	META-INF/db2-jpa-changelog-1.4.0.xml	2023-11-16 09:20:24.787775	12	MARK_RAN	9:e1ff28bf7568451453f844c5d54bb0b5	delete tableName=CLIENT_SESSION_AUTH_STATUS; delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_PROT_MAPPER; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete table...		\N	4.23.2	\N	\N	0126422430
1.5.0	bburke@redhat.com	META-INF/jpa-changelog-1.5.0.xml	2023-11-16 09:20:24.815877	13	EXECUTED	9:7af32cd8957fbc069f796b61217483fd	delete tableName=CLIENT_SESSION_AUTH_STATUS; delete tableName=CLIENT_SESSION_ROLE; delete tableName=CLIENT_SESSION_PROT_MAPPER; delete tableName=CLIENT_SESSION_NOTE; delete tableName=CLIENT_SESSION; delete tableName=USER_SESSION_NOTE; delete table...		\N	4.23.2	\N	\N	0126422430
1.6.1_from15	mposolda@redhat.com	META-INF/jpa-changelog-1.6.1.xml	2023-11-16 09:20:24.876143	14	EXECUTED	9:6005e15e84714cd83226bf7879f54190	addColumn tableName=REALM; addColumn tableName=KEYCLOAK_ROLE; addColumn tableName=CLIENT; createTable tableName=OFFLINE_USER_SESSION; createTable tableName=OFFLINE_CLIENT_SESSION; addPrimaryKey constraintName=CONSTRAINT_OFFL_US_SES_PK2, tableName=...		\N	4.23.2	\N	\N	0126422430
1.6.1_from16-pre	mposolda@redhat.com	META-INF/jpa-changelog-1.6.1.xml	2023-11-16 09:20:24.882406	15	MARK_RAN	9:bf656f5a2b055d07f314431cae76f06c	delete tableName=OFFLINE_CLIENT_SESSION; delete tableName=OFFLINE_USER_SESSION		\N	4.23.2	\N	\N	0126422430
1.6.1_from16	mposolda@redhat.com	META-INF/jpa-changelog-1.6.1.xml	2023-11-16 09:20:24.889704	16	MARK_RAN	9:f8dadc9284440469dcf71e25ca6ab99b	dropPrimaryKey constraintName=CONSTRAINT_OFFLINE_US_SES_PK, tableName=OFFLINE_USER_SESSION; dropPrimaryKey constraintName=CONSTRAINT_OFFLINE_CL_SES_PK, tableName=OFFLINE_CLIENT_SESSION; addColumn tableName=OFFLINE_USER_SESSION; update tableName=OF...		\N	4.23.2	\N	\N	0126422430
1.6.1	mposolda@redhat.com	META-INF/jpa-changelog-1.6.1.xml	2023-11-16 09:20:24.897008	17	EXECUTED	9:d41d8cd98f00b204e9800998ecf8427e	empty		\N	4.23.2	\N	\N	0126422430
1.7.0	bburke@redhat.com	META-INF/jpa-changelog-1.7.0.xml	2023-11-16 09:20:24.996034	18	EXECUTED	9:3368ff0be4c2855ee2dd9ca813b38d8e	createTable tableName=KEYCLOAK_GROUP; createTable tableName=GROUP_ROLE_MAPPING; createTable tableName=GROUP_ATTRIBUTE; createTable tableName=USER_GROUP_MEMBERSHIP; createTable tableName=REALM_DEFAULT_GROUPS; addColumn tableName=IDENTITY_PROVIDER; ...		\N	4.23.2	\N	\N	0126422430
1.8.0	mposolda@redhat.com	META-INF/jpa-changelog-1.8.0.xml	2023-11-16 09:20:25.086732	19	EXECUTED	9:8ac2fb5dd030b24c0570a763ed75ed20	addColumn tableName=IDENTITY_PROVIDER; createTable tableName=CLIENT_TEMPLATE; createTable tableName=CLIENT_TEMPLATE_ATTRIBUTES; createTable tableName=TEMPLATE_SCOPE_MAPPING; dropNotNullConstraint columnName=CLIENT_ID, tableName=PROTOCOL_MAPPER; ad...		\N	4.23.2	\N	\N	0126422430
1.8.0-2	keycloak	META-INF/jpa-changelog-1.8.0.xml	2023-11-16 09:20:25.098802	20	EXECUTED	9:f91ddca9b19743db60e3057679810e6c	dropDefaultValue columnName=ALGORITHM, tableName=CREDENTIAL; update tableName=CREDENTIAL		\N	4.23.2	\N	\N	0126422430
1.8.0	mposolda@redhat.com	META-INF/db2-jpa-changelog-1.8.0.xml	2023-11-16 09:20:25.11213	21	MARK_RAN	9:831e82914316dc8a57dc09d755f23c51	addColumn tableName=IDENTITY_PROVIDER; createTable tableName=CLIENT_TEMPLATE; createTable tableName=CLIENT_TEMPLATE_ATTRIBUTES; createTable tableName=TEMPLATE_SCOPE_MAPPING; dropNotNullConstraint columnName=CLIENT_ID, tableName=PROTOCOL_MAPPER; ad...		\N	4.23.2	\N	\N	0126422430
1.8.0-2	keycloak	META-INF/db2-jpa-changelog-1.8.0.xml	2023-11-16 09:20:25.119645	22	MARK_RAN	9:f91ddca9b19743db60e3057679810e6c	dropDefaultValue columnName=ALGORITHM, tableName=CREDENTIAL; update tableName=CREDENTIAL		\N	4.23.2	\N	\N	0126422430
1.9.0	mposolda@redhat.com	META-INF/jpa-changelog-1.9.0.xml	2023-11-16 09:20:25.165889	23	EXECUTED	9:bc3d0f9e823a69dc21e23e94c7a94bb1	update tableName=REALM; update tableName=REALM; update tableName=REALM; update tableName=REALM; update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=REALM; update tableName=REALM; customChange; dr...		\N	4.23.2	\N	\N	0126422430
1.9.1	keycloak	META-INF/jpa-changelog-1.9.1.xml	2023-11-16 09:20:25.17997	24	EXECUTED	9:c9999da42f543575ab790e76439a2679	modifyDataType columnName=PRIVATE_KEY, tableName=REALM; modifyDataType columnName=PUBLIC_KEY, tableName=REALM; modifyDataType columnName=CERTIFICATE, tableName=REALM		\N	4.23.2	\N	\N	0126422430
1.9.1	keycloak	META-INF/db2-jpa-changelog-1.9.1.xml	2023-11-16 09:20:25.185222	25	MARK_RAN	9:0d6c65c6f58732d81569e77b10ba301d	modifyDataType columnName=PRIVATE_KEY, tableName=REALM; modifyDataType columnName=CERTIFICATE, tableName=REALM		\N	4.23.2	\N	\N	0126422430
1.9.2	keycloak	META-INF/jpa-changelog-1.9.2.xml	2023-11-16 09:20:25.298418	26	EXECUTED	9:fc576660fc016ae53d2d4778d84d86d0	createIndex indexName=IDX_USER_EMAIL, tableName=USER_ENTITY; createIndex indexName=IDX_USER_ROLE_MAPPING, tableName=USER_ROLE_MAPPING; createIndex indexName=IDX_USER_GROUP_MAPPING, tableName=USER_GROUP_MEMBERSHIP; createIndex indexName=IDX_USER_CO...		\N	4.23.2	\N	\N	0126422430
authz-2.0.0	psilva@redhat.com	META-INF/jpa-changelog-authz-2.0.0.xml	2023-11-16 09:20:25.512803	27	EXECUTED	9:43ed6b0da89ff77206289e87eaa9c024	createTable tableName=RESOURCE_SERVER; addPrimaryKey constraintName=CONSTRAINT_FARS, tableName=RESOURCE_SERVER; addUniqueConstraint constraintName=UK_AU8TT6T700S9V50BU18WS5HA6, tableName=RESOURCE_SERVER; createTable tableName=RESOURCE_SERVER_RESOU...		\N	4.23.2	\N	\N	0126422430
authz-2.5.1	psilva@redhat.com	META-INF/jpa-changelog-authz-2.5.1.xml	2023-11-16 09:20:25.52027	28	EXECUTED	9:44bae577f551b3738740281eceb4ea70	update tableName=RESOURCE_SERVER_POLICY		\N	4.23.2	\N	\N	0126422430
2.1.0-KEYCLOAK-5461	bburke@redhat.com	META-INF/jpa-changelog-2.1.0.xml	2023-11-16 09:20:25.709593	29	EXECUTED	9:bd88e1f833df0420b01e114533aee5e8	createTable tableName=BROKER_LINK; createTable tableName=FED_USER_ATTRIBUTE; createTable tableName=FED_USER_CONSENT; createTable tableName=FED_USER_CONSENT_ROLE; createTable tableName=FED_USER_CONSENT_PROT_MAPPER; createTable tableName=FED_USER_CR...		\N	4.23.2	\N	\N	0126422430
2.2.0	bburke@redhat.com	META-INF/jpa-changelog-2.2.0.xml	2023-11-16 09:20:25.746061	30	EXECUTED	9:a7022af5267f019d020edfe316ef4371	addColumn tableName=ADMIN_EVENT_ENTITY; createTable tableName=CREDENTIAL_ATTRIBUTE; createTable tableName=FED_CREDENTIAL_ATTRIBUTE; modifyDataType columnName=VALUE, tableName=CREDENTIAL; addForeignKeyConstraint baseTableName=FED_CREDENTIAL_ATTRIBU...		\N	4.23.2	\N	\N	0126422430
2.3.0	bburke@redhat.com	META-INF/jpa-changelog-2.3.0.xml	2023-11-16 09:20:25.786403	31	EXECUTED	9:fc155c394040654d6a79227e56f5e25a	createTable tableName=FEDERATED_USER; addPrimaryKey constraintName=CONSTR_FEDERATED_USER, tableName=FEDERATED_USER; dropDefaultValue columnName=TOTP, tableName=USER_ENTITY; dropColumn columnName=TOTP, tableName=USER_ENTITY; addColumn tableName=IDE...		\N	4.23.2	\N	\N	0126422430
2.4.0	bburke@redhat.com	META-INF/jpa-changelog-2.4.0.xml	2023-11-16 09:20:25.7947	32	EXECUTED	9:eac4ffb2a14795e5dc7b426063e54d88	customChange		\N	4.23.2	\N	\N	0126422430
2.5.0	bburke@redhat.com	META-INF/jpa-changelog-2.5.0.xml	2023-11-16 09:20:25.806958	33	EXECUTED	9:54937c05672568c4c64fc9524c1e9462	customChange; modifyDataType columnName=USER_ID, tableName=OFFLINE_USER_SESSION		\N	4.23.2	\N	\N	0126422430
2.5.0-unicode-oracle	hmlnarik@redhat.com	META-INF/jpa-changelog-2.5.0.xml	2023-11-16 09:20:25.813895	34	MARK_RAN	9:3a32bace77c84d7678d035a7f5a8084e	modifyDataType columnName=DESCRIPTION, tableName=AUTHENTICATION_FLOW; modifyDataType columnName=DESCRIPTION, tableName=CLIENT_TEMPLATE; modifyDataType columnName=DESCRIPTION, tableName=RESOURCE_SERVER_POLICY; modifyDataType columnName=DESCRIPTION,...		\N	4.23.2	\N	\N	0126422430
2.5.0-unicode-other-dbs	hmlnarik@redhat.com	META-INF/jpa-changelog-2.5.0.xml	2023-11-16 09:20:25.89727	35	EXECUTED	9:33d72168746f81f98ae3a1e8e0ca3554	modifyDataType columnName=DESCRIPTION, tableName=AUTHENTICATION_FLOW; modifyDataType columnName=DESCRIPTION, tableName=CLIENT_TEMPLATE; modifyDataType columnName=DESCRIPTION, tableName=RESOURCE_SERVER_POLICY; modifyDataType columnName=DESCRIPTION,...		\N	4.23.2	\N	\N	0126422430
2.5.0-duplicate-email-support	slawomir@dabek.name	META-INF/jpa-changelog-2.5.0.xml	2023-11-16 09:20:25.909009	36	EXECUTED	9:61b6d3d7a4c0e0024b0c839da283da0c	addColumn tableName=REALM		\N	4.23.2	\N	\N	0126422430
2.5.0-unique-group-names	hmlnarik@redhat.com	META-INF/jpa-changelog-2.5.0.xml	2023-11-16 09:20:25.928697	37	EXECUTED	9:8dcac7bdf7378e7d823cdfddebf72fda	addUniqueConstraint constraintName=SIBLING_NAMES, tableName=KEYCLOAK_GROUP		\N	4.23.2	\N	\N	0126422430
2.5.1	bburke@redhat.com	META-INF/jpa-changelog-2.5.1.xml	2023-11-16 09:20:25.939506	38	EXECUTED	9:a2b870802540cb3faa72098db5388af3	addColumn tableName=FED_USER_CONSENT		\N	4.23.2	\N	\N	0126422430
3.0.0	bburke@redhat.com	META-INF/jpa-changelog-3.0.0.xml	2023-11-16 09:20:25.949923	39	EXECUTED	9:132a67499ba24bcc54fb5cbdcfe7e4c0	addColumn tableName=IDENTITY_PROVIDER		\N	4.23.2	\N	\N	0126422430
3.2.0-fix	keycloak	META-INF/jpa-changelog-3.2.0.xml	2023-11-16 09:20:25.955025	40	MARK_RAN	9:938f894c032f5430f2b0fafb1a243462	addNotNullConstraint columnName=REALM_ID, tableName=CLIENT_INITIAL_ACCESS		\N	4.23.2	\N	\N	0126422430
3.2.0-fix-with-keycloak-5416	keycloak	META-INF/jpa-changelog-3.2.0.xml	2023-11-16 09:20:25.9612	41	MARK_RAN	9:845c332ff1874dc5d35974b0babf3006	dropIndex indexName=IDX_CLIENT_INIT_ACC_REALM, tableName=CLIENT_INITIAL_ACCESS; addNotNullConstraint columnName=REALM_ID, tableName=CLIENT_INITIAL_ACCESS; createIndex indexName=IDX_CLIENT_INIT_ACC_REALM, tableName=CLIENT_INITIAL_ACCESS		\N	4.23.2	\N	\N	0126422430
3.2.0-fix-offline-sessions	hmlnarik	META-INF/jpa-changelog-3.2.0.xml	2023-11-16 09:20:25.969648	42	EXECUTED	9:fc86359c079781adc577c5a217e4d04c	customChange		\N	4.23.2	\N	\N	0126422430
3.2.0-fixed	keycloak	META-INF/jpa-changelog-3.2.0.xml	2023-11-16 09:20:26.432943	43	EXECUTED	9:59a64800e3c0d09b825f8a3b444fa8f4	addColumn tableName=REALM; dropPrimaryKey constraintName=CONSTRAINT_OFFL_CL_SES_PK2, tableName=OFFLINE_CLIENT_SESSION; dropColumn columnName=CLIENT_SESSION_ID, tableName=OFFLINE_CLIENT_SESSION; addPrimaryKey constraintName=CONSTRAINT_OFFL_CL_SES_P...		\N	4.23.2	\N	\N	0126422430
3.3.0	keycloak	META-INF/jpa-changelog-3.3.0.xml	2023-11-16 09:20:26.44393	44	EXECUTED	9:d48d6da5c6ccf667807f633fe489ce88	addColumn tableName=USER_ENTITY		\N	4.23.2	\N	\N	0126422430
authz-3.4.0.CR1-resource-server-pk-change-part1	glavoie@gmail.com	META-INF/jpa-changelog-authz-3.4.0.CR1.xml	2023-11-16 09:20:26.454776	45	EXECUTED	9:dde36f7973e80d71fceee683bc5d2951	addColumn tableName=RESOURCE_SERVER_POLICY; addColumn tableName=RESOURCE_SERVER_RESOURCE; addColumn tableName=RESOURCE_SERVER_SCOPE		\N	4.23.2	\N	\N	0126422430
authz-3.4.0.CR1-resource-server-pk-change-part2-KEYCLOAK-6095	hmlnarik@redhat.com	META-INF/jpa-changelog-authz-3.4.0.CR1.xml	2023-11-16 09:20:26.462161	46	EXECUTED	9:b855e9b0a406b34fa323235a0cf4f640	customChange		\N	4.23.2	\N	\N	0126422430
authz-3.4.0.CR1-resource-server-pk-change-part3-fixed	glavoie@gmail.com	META-INF/jpa-changelog-authz-3.4.0.CR1.xml	2023-11-16 09:20:26.467103	47	MARK_RAN	9:51abbacd7b416c50c4421a8cabf7927e	dropIndex indexName=IDX_RES_SERV_POL_RES_SERV, tableName=RESOURCE_SERVER_POLICY; dropIndex indexName=IDX_RES_SRV_RES_RES_SRV, tableName=RESOURCE_SERVER_RESOURCE; dropIndex indexName=IDX_RES_SRV_SCOPE_RES_SRV, tableName=RESOURCE_SERVER_SCOPE		\N	4.23.2	\N	\N	0126422430
authz-3.4.0.CR1-resource-server-pk-change-part3-fixed-nodropindex	glavoie@gmail.com	META-INF/jpa-changelog-authz-3.4.0.CR1.xml	2023-11-16 09:20:26.557628	48	EXECUTED	9:bdc99e567b3398bac83263d375aad143	addNotNullConstraint columnName=RESOURCE_SERVER_CLIENT_ID, tableName=RESOURCE_SERVER_POLICY; addNotNullConstraint columnName=RESOURCE_SERVER_CLIENT_ID, tableName=RESOURCE_SERVER_RESOURCE; addNotNullConstraint columnName=RESOURCE_SERVER_CLIENT_ID, ...		\N	4.23.2	\N	\N	0126422430
authn-3.4.0.CR1-refresh-token-max-reuse	glavoie@gmail.com	META-INF/jpa-changelog-authz-3.4.0.CR1.xml	2023-11-16 09:20:26.568552	49	EXECUTED	9:d198654156881c46bfba39abd7769e69	addColumn tableName=REALM		\N	4.23.2	\N	\N	0126422430
3.4.0	keycloak	META-INF/jpa-changelog-3.4.0.xml	2023-11-16 09:20:26.712482	50	EXECUTED	9:cfdd8736332ccdd72c5256ccb42335db	addPrimaryKey constraintName=CONSTRAINT_REALM_DEFAULT_ROLES, tableName=REALM_DEFAULT_ROLES; addPrimaryKey constraintName=CONSTRAINT_COMPOSITE_ROLE, tableName=COMPOSITE_ROLE; addPrimaryKey constraintName=CONSTR_REALM_DEFAULT_GROUPS, tableName=REALM...		\N	4.23.2	\N	\N	0126422430
3.4.0-KEYCLOAK-5230	hmlnarik@redhat.com	META-INF/jpa-changelog-3.4.0.xml	2023-11-16 09:20:26.84961	51	EXECUTED	9:7c84de3d9bd84d7f077607c1a4dcb714	createIndex indexName=IDX_FU_ATTRIBUTE, tableName=FED_USER_ATTRIBUTE; createIndex indexName=IDX_FU_CONSENT, tableName=FED_USER_CONSENT; createIndex indexName=IDX_FU_CONSENT_RU, tableName=FED_USER_CONSENT; createIndex indexName=IDX_FU_CREDENTIAL, t...		\N	4.23.2	\N	\N	0126422430
3.4.1	psilva@redhat.com	META-INF/jpa-changelog-3.4.1.xml	2023-11-16 09:20:26.862009	52	EXECUTED	9:5a6bb36cbefb6a9d6928452c0852af2d	modifyDataType columnName=VALUE, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
3.4.2	keycloak	META-INF/jpa-changelog-3.4.2.xml	2023-11-16 09:20:26.868511	53	EXECUTED	9:8f23e334dbc59f82e0a328373ca6ced0	update tableName=REALM		\N	4.23.2	\N	\N	0126422430
3.4.2-KEYCLOAK-5172	mkanis@redhat.com	META-INF/jpa-changelog-3.4.2.xml	2023-11-16 09:20:26.878753	54	EXECUTED	9:9156214268f09d970cdf0e1564d866af	update tableName=CLIENT		\N	4.23.2	\N	\N	0126422430
4.0.0-KEYCLOAK-6335	bburke@redhat.com	META-INF/jpa-changelog-4.0.0.xml	2023-11-16 09:20:26.897646	55	EXECUTED	9:db806613b1ed154826c02610b7dbdf74	createTable tableName=CLIENT_AUTH_FLOW_BINDINGS; addPrimaryKey constraintName=C_CLI_FLOW_BIND, tableName=CLIENT_AUTH_FLOW_BINDINGS		\N	4.23.2	\N	\N	0126422430
4.0.0-CLEANUP-UNUSED-TABLE	bburke@redhat.com	META-INF/jpa-changelog-4.0.0.xml	2023-11-16 09:20:26.911923	56	EXECUTED	9:229a041fb72d5beac76bb94a5fa709de	dropTable tableName=CLIENT_IDENTITY_PROV_MAPPING		\N	4.23.2	\N	\N	0126422430
4.0.0-KEYCLOAK-6228	bburke@redhat.com	META-INF/jpa-changelog-4.0.0.xml	2023-11-16 09:20:26.975626	57	EXECUTED	9:079899dade9c1e683f26b2aa9ca6ff04	dropUniqueConstraint constraintName=UK_JKUWUVD56ONTGSUHOGM8UEWRT, tableName=USER_CONSENT; dropNotNullConstraint columnName=CLIENT_ID, tableName=USER_CONSENT; addColumn tableName=USER_CONSENT; addUniqueConstraint constraintName=UK_JKUWUVD56ONTGSUHO...		\N	4.23.2	\N	\N	0126422430
4.0.0-KEYCLOAK-5579-fixed	mposolda@redhat.com	META-INF/jpa-changelog-4.0.0.xml	2023-11-16 09:20:27.194368	58	EXECUTED	9:139b79bcbbfe903bb1c2d2a4dbf001d9	dropForeignKeyConstraint baseTableName=CLIENT_TEMPLATE_ATTRIBUTES, constraintName=FK_CL_TEMPL_ATTR_TEMPL; renameTable newTableName=CLIENT_SCOPE_ATTRIBUTES, oldTableName=CLIENT_TEMPLATE_ATTRIBUTES; renameColumn newColumnName=SCOPE_ID, oldColumnName...		\N	4.23.2	\N	\N	0126422430
authz-4.0.0.CR1	psilva@redhat.com	META-INF/jpa-changelog-authz-4.0.0.CR1.xml	2023-11-16 09:20:27.262718	59	EXECUTED	9:b55738ad889860c625ba2bf483495a04	createTable tableName=RESOURCE_SERVER_PERM_TICKET; addPrimaryKey constraintName=CONSTRAINT_FAPMT, tableName=RESOURCE_SERVER_PERM_TICKET; addForeignKeyConstraint baseTableName=RESOURCE_SERVER_PERM_TICKET, constraintName=FK_FRSRHO213XCX4WNKOG82SSPMT...		\N	4.23.2	\N	\N	0126422430
authz-4.0.0.Beta3	psilva@redhat.com	META-INF/jpa-changelog-authz-4.0.0.Beta3.xml	2023-11-16 09:20:27.275572	60	EXECUTED	9:e0057eac39aa8fc8e09ac6cfa4ae15fe	addColumn tableName=RESOURCE_SERVER_POLICY; addColumn tableName=RESOURCE_SERVER_PERM_TICKET; addForeignKeyConstraint baseTableName=RESOURCE_SERVER_PERM_TICKET, constraintName=FK_FRSRPO2128CX4WNKOG82SSRFY, referencedTableName=RESOURCE_SERVER_POLICY		\N	4.23.2	\N	\N	0126422430
authz-4.2.0.Final	mhajas@redhat.com	META-INF/jpa-changelog-authz-4.2.0.Final.xml	2023-11-16 09:20:27.290329	61	EXECUTED	9:42a33806f3a0443fe0e7feeec821326c	createTable tableName=RESOURCE_URIS; addForeignKeyConstraint baseTableName=RESOURCE_URIS, constraintName=FK_RESOURCE_SERVER_URIS, referencedTableName=RESOURCE_SERVER_RESOURCE; customChange; dropColumn columnName=URI, tableName=RESOURCE_SERVER_RESO...		\N	4.23.2	\N	\N	0126422430
authz-4.2.0.Final-KEYCLOAK-9944	hmlnarik@redhat.com	META-INF/jpa-changelog-authz-4.2.0.Final.xml	2023-11-16 09:20:27.308721	62	EXECUTED	9:9968206fca46eecc1f51db9c024bfe56	addPrimaryKey constraintName=CONSTRAINT_RESOUR_URIS_PK, tableName=RESOURCE_URIS		\N	4.23.2	\N	\N	0126422430
4.2.0-KEYCLOAK-6313	wadahiro@gmail.com	META-INF/jpa-changelog-4.2.0.xml	2023-11-16 09:20:27.318629	63	EXECUTED	9:92143a6daea0a3f3b8f598c97ce55c3d	addColumn tableName=REQUIRED_ACTION_PROVIDER		\N	4.23.2	\N	\N	0126422430
4.3.0-KEYCLOAK-7984	wadahiro@gmail.com	META-INF/jpa-changelog-4.3.0.xml	2023-11-16 09:20:27.325113	64	EXECUTED	9:82bab26a27195d889fb0429003b18f40	update tableName=REQUIRED_ACTION_PROVIDER		\N	4.23.2	\N	\N	0126422430
4.6.0-KEYCLOAK-7950	psilva@redhat.com	META-INF/jpa-changelog-4.6.0.xml	2023-11-16 09:20:27.331649	65	EXECUTED	9:e590c88ddc0b38b0ae4249bbfcb5abc3	update tableName=RESOURCE_SERVER_RESOURCE		\N	4.23.2	\N	\N	0126422430
4.6.0-KEYCLOAK-8377	keycloak	META-INF/jpa-changelog-4.6.0.xml	2023-11-16 09:20:27.370505	66	EXECUTED	9:5c1f475536118dbdc38d5d7977950cc0	createTable tableName=ROLE_ATTRIBUTE; addPrimaryKey constraintName=CONSTRAINT_ROLE_ATTRIBUTE_PK, tableName=ROLE_ATTRIBUTE; addForeignKeyConstraint baseTableName=ROLE_ATTRIBUTE, constraintName=FK_ROLE_ATTRIBUTE_ID, referencedTableName=KEYCLOAK_ROLE...		\N	4.23.2	\N	\N	0126422430
4.6.0-KEYCLOAK-8555	gideonray@gmail.com	META-INF/jpa-changelog-4.6.0.xml	2023-11-16 09:20:27.397154	67	EXECUTED	9:e7c9f5f9c4d67ccbbcc215440c718a17	createIndex indexName=IDX_COMPONENT_PROVIDER_TYPE, tableName=COMPONENT		\N	4.23.2	\N	\N	0126422430
4.7.0-KEYCLOAK-1267	sguilhen@redhat.com	META-INF/jpa-changelog-4.7.0.xml	2023-11-16 09:20:27.40993	68	EXECUTED	9:88e0bfdda924690d6f4e430c53447dd5	addColumn tableName=REALM		\N	4.23.2	\N	\N	0126422430
4.7.0-KEYCLOAK-7275	keycloak	META-INF/jpa-changelog-4.7.0.xml	2023-11-16 09:20:27.43457	69	EXECUTED	9:f53177f137e1c46b6a88c59ec1cb5218	renameColumn newColumnName=CREATED_ON, oldColumnName=LAST_SESSION_REFRESH, tableName=OFFLINE_USER_SESSION; addNotNullConstraint columnName=CREATED_ON, tableName=OFFLINE_USER_SESSION; addColumn tableName=OFFLINE_USER_SESSION; customChange; createIn...		\N	4.23.2	\N	\N	0126422430
4.8.0-KEYCLOAK-8835	sguilhen@redhat.com	META-INF/jpa-changelog-4.8.0.xml	2023-11-16 09:20:27.447166	70	EXECUTED	9:a74d33da4dc42a37ec27121580d1459f	addNotNullConstraint columnName=SSO_MAX_LIFESPAN_REMEMBER_ME, tableName=REALM; addNotNullConstraint columnName=SSO_IDLE_TIMEOUT_REMEMBER_ME, tableName=REALM		\N	4.23.2	\N	\N	0126422430
authz-7.0.0-KEYCLOAK-10443	psilva@redhat.com	META-INF/jpa-changelog-authz-7.0.0.xml	2023-11-16 09:20:27.458375	71	EXECUTED	9:fd4ade7b90c3b67fae0bfcfcb42dfb5f	addColumn tableName=RESOURCE_SERVER		\N	4.23.2	\N	\N	0126422430
8.0.0-adding-credential-columns	keycloak	META-INF/jpa-changelog-8.0.0.xml	2023-11-16 09:20:27.473738	72	EXECUTED	9:aa072ad090bbba210d8f18781b8cebf4	addColumn tableName=CREDENTIAL; addColumn tableName=FED_USER_CREDENTIAL		\N	4.23.2	\N	\N	0126422430
8.0.0-updating-credential-data-not-oracle-fixed	keycloak	META-INF/jpa-changelog-8.0.0.xml	2023-11-16 09:20:27.485372	73	EXECUTED	9:1ae6be29bab7c2aa376f6983b932be37	update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=FED_USER_CREDENTIAL; update tableName=FED_USER_CREDENTIAL; update tableName=FED_USER_CREDENTIAL		\N	4.23.2	\N	\N	0126422430
8.0.0-updating-credential-data-oracle-fixed	keycloak	META-INF/jpa-changelog-8.0.0.xml	2023-11-16 09:20:27.49202	74	MARK_RAN	9:14706f286953fc9a25286dbd8fb30d97	update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=CREDENTIAL; update tableName=FED_USER_CREDENTIAL; update tableName=FED_USER_CREDENTIAL; update tableName=FED_USER_CREDENTIAL		\N	4.23.2	\N	\N	0126422430
8.0.0-credential-cleanup-fixed	keycloak	META-INF/jpa-changelog-8.0.0.xml	2023-11-16 09:20:27.519764	75	EXECUTED	9:2b9cc12779be32c5b40e2e67711a218b	dropDefaultValue columnName=COUNTER, tableName=CREDENTIAL; dropDefaultValue columnName=DIGITS, tableName=CREDENTIAL; dropDefaultValue columnName=PERIOD, tableName=CREDENTIAL; dropDefaultValue columnName=ALGORITHM, tableName=CREDENTIAL; dropColumn ...		\N	4.23.2	\N	\N	0126422430
8.0.0-resource-tag-support	keycloak	META-INF/jpa-changelog-8.0.0.xml	2023-11-16 09:20:27.539368	76	EXECUTED	9:91fa186ce7a5af127a2d7a91ee083cc5	addColumn tableName=MIGRATION_MODEL; createIndex indexName=IDX_UPDATE_TIME, tableName=MIGRATION_MODEL		\N	4.23.2	\N	\N	0126422430
9.0.0-always-display-client	keycloak	META-INF/jpa-changelog-9.0.0.xml	2023-11-16 09:20:27.549524	77	EXECUTED	9:6335e5c94e83a2639ccd68dd24e2e5ad	addColumn tableName=CLIENT		\N	4.23.2	\N	\N	0126422430
9.0.0-drop-constraints-for-column-increase	keycloak	META-INF/jpa-changelog-9.0.0.xml	2023-11-16 09:20:27.558494	78	MARK_RAN	9:6bdb5658951e028bfe16fa0a8228b530	dropUniqueConstraint constraintName=UK_FRSR6T700S9V50BU18WS5PMT, tableName=RESOURCE_SERVER_PERM_TICKET; dropUniqueConstraint constraintName=UK_FRSR6T700S9V50BU18WS5HA6, tableName=RESOURCE_SERVER_RESOURCE; dropPrimaryKey constraintName=CONSTRAINT_O...		\N	4.23.2	\N	\N	0126422430
9.0.0-increase-column-size-federated-fk	keycloak	META-INF/jpa-changelog-9.0.0.xml	2023-11-16 09:20:27.601321	79	EXECUTED	9:d5bc15a64117ccad481ce8792d4c608f	modifyDataType columnName=CLIENT_ID, tableName=FED_USER_CONSENT; modifyDataType columnName=CLIENT_REALM_CONSTRAINT, tableName=KEYCLOAK_ROLE; modifyDataType columnName=OWNER, tableName=RESOURCE_SERVER_POLICY; modifyDataType columnName=CLIENT_ID, ta...		\N	4.23.2	\N	\N	0126422430
9.0.0-recreate-constraints-after-column-increase	keycloak	META-INF/jpa-changelog-9.0.0.xml	2023-11-16 09:20:27.608953	80	MARK_RAN	9:077cba51999515f4d3e7ad5619ab592c	addNotNullConstraint columnName=CLIENT_ID, tableName=OFFLINE_CLIENT_SESSION; addNotNullConstraint columnName=OWNER, tableName=RESOURCE_SERVER_PERM_TICKET; addNotNullConstraint columnName=REQUESTER, tableName=RESOURCE_SERVER_PERM_TICKET; addNotNull...		\N	4.23.2	\N	\N	0126422430
9.0.1-add-index-to-client.client_id	keycloak	META-INF/jpa-changelog-9.0.1.xml	2023-11-16 09:20:27.630714	81	EXECUTED	9:be969f08a163bf47c6b9e9ead8ac2afb	createIndex indexName=IDX_CLIENT_ID, tableName=CLIENT		\N	4.23.2	\N	\N	0126422430
9.0.1-KEYCLOAK-12579-drop-constraints	keycloak	META-INF/jpa-changelog-9.0.1.xml	2023-11-16 09:20:27.635847	82	MARK_RAN	9:6d3bb4408ba5a72f39bd8a0b301ec6e3	dropUniqueConstraint constraintName=SIBLING_NAMES, tableName=KEYCLOAK_GROUP		\N	4.23.2	\N	\N	0126422430
9.0.1-KEYCLOAK-12579-add-not-null-constraint	keycloak	META-INF/jpa-changelog-9.0.1.xml	2023-11-16 09:20:27.648042	83	EXECUTED	9:966bda61e46bebf3cc39518fbed52fa7	addNotNullConstraint columnName=PARENT_GROUP, tableName=KEYCLOAK_GROUP		\N	4.23.2	\N	\N	0126422430
9.0.1-KEYCLOAK-12579-recreate-constraints	keycloak	META-INF/jpa-changelog-9.0.1.xml	2023-11-16 09:20:27.653462	84	MARK_RAN	9:8dcac7bdf7378e7d823cdfddebf72fda	addUniqueConstraint constraintName=SIBLING_NAMES, tableName=KEYCLOAK_GROUP		\N	4.23.2	\N	\N	0126422430
9.0.1-add-index-to-events	keycloak	META-INF/jpa-changelog-9.0.1.xml	2023-11-16 09:20:27.673457	85	EXECUTED	9:7d93d602352a30c0c317e6a609b56599	createIndex indexName=IDX_EVENT_TIME, tableName=EVENT_ENTITY		\N	4.23.2	\N	\N	0126422430
map-remove-ri	keycloak	META-INF/jpa-changelog-11.0.0.xml	2023-11-16 09:20:27.685251	86	EXECUTED	9:71c5969e6cdd8d7b6f47cebc86d37627	dropForeignKeyConstraint baseTableName=REALM, constraintName=FK_TRAF444KK6QRKMS7N56AIWQ5Y; dropForeignKeyConstraint baseTableName=KEYCLOAK_ROLE, constraintName=FK_KJHO5LE2C0RAL09FL8CM9WFW9		\N	4.23.2	\N	\N	0126422430
map-remove-ri	keycloak	META-INF/jpa-changelog-12.0.0.xml	2023-11-16 09:20:27.699461	87	EXECUTED	9:a9ba7d47f065f041b7da856a81762021	dropForeignKeyConstraint baseTableName=REALM_DEFAULT_GROUPS, constraintName=FK_DEF_GROUPS_GROUP; dropForeignKeyConstraint baseTableName=REALM_DEFAULT_ROLES, constraintName=FK_H4WPD7W4HSOOLNI3H0SW7BTJE; dropForeignKeyConstraint baseTableName=CLIENT...		\N	4.23.2	\N	\N	0126422430
12.1.0-add-realm-localization-table	keycloak	META-INF/jpa-changelog-12.0.0.xml	2023-11-16 09:20:27.728278	88	EXECUTED	9:fffabce2bc01e1a8f5110d5278500065	createTable tableName=REALM_LOCALIZATIONS; addPrimaryKey tableName=REALM_LOCALIZATIONS		\N	4.23.2	\N	\N	0126422430
default-roles	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.744107	89	EXECUTED	9:fa8a5b5445e3857f4b010bafb5009957	addColumn tableName=REALM; customChange		\N	4.23.2	\N	\N	0126422430
default-roles-cleanup	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.756583	90	EXECUTED	9:67ac3241df9a8582d591c5ed87125f39	dropTable tableName=REALM_DEFAULT_ROLES; dropTable tableName=CLIENT_DEFAULT_ROLES		\N	4.23.2	\N	\N	0126422430
13.0.0-KEYCLOAK-16844	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.775674	91	EXECUTED	9:ad1194d66c937e3ffc82386c050ba089	createIndex indexName=IDX_OFFLINE_USS_PRELOAD, tableName=OFFLINE_USER_SESSION		\N	4.23.2	\N	\N	0126422430
map-remove-ri-13.0.0	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.789821	92	EXECUTED	9:d9be619d94af5a2f5d07b9f003543b91	dropForeignKeyConstraint baseTableName=DEFAULT_CLIENT_SCOPE, constraintName=FK_R_DEF_CLI_SCOPE_SCOPE; dropForeignKeyConstraint baseTableName=CLIENT_SCOPE_CLIENT, constraintName=FK_C_CLI_SCOPE_SCOPE; dropForeignKeyConstraint baseTableName=CLIENT_SC...		\N	4.23.2	\N	\N	0126422430
13.0.0-KEYCLOAK-17992-drop-constraints	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.795297	93	MARK_RAN	9:544d201116a0fcc5a5da0925fbbc3bde	dropPrimaryKey constraintName=C_CLI_SCOPE_BIND, tableName=CLIENT_SCOPE_CLIENT; dropIndex indexName=IDX_CLSCOPE_CL, tableName=CLIENT_SCOPE_CLIENT; dropIndex indexName=IDX_CL_CLSCOPE, tableName=CLIENT_SCOPE_CLIENT		\N	4.23.2	\N	\N	0126422430
13.0.0-increase-column-size-federated	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.817835	94	EXECUTED	9:43c0c1055b6761b4b3e89de76d612ccf	modifyDataType columnName=CLIENT_ID, tableName=CLIENT_SCOPE_CLIENT; modifyDataType columnName=SCOPE_ID, tableName=CLIENT_SCOPE_CLIENT		\N	4.23.2	\N	\N	0126422430
13.0.0-KEYCLOAK-17992-recreate-constraints	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.82368	95	MARK_RAN	9:8bd711fd0330f4fe980494ca43ab1139	addNotNullConstraint columnName=CLIENT_ID, tableName=CLIENT_SCOPE_CLIENT; addNotNullConstraint columnName=SCOPE_ID, tableName=CLIENT_SCOPE_CLIENT; addPrimaryKey constraintName=C_CLI_SCOPE_BIND, tableName=CLIENT_SCOPE_CLIENT; createIndex indexName=...		\N	4.23.2	\N	\N	0126422430
json-string-accomodation-fixed	keycloak	META-INF/jpa-changelog-13.0.0.xml	2023-11-16 09:20:27.836709	96	EXECUTED	9:e07d2bc0970c348bb06fb63b1f82ddbf	addColumn tableName=REALM_ATTRIBUTE; update tableName=REALM_ATTRIBUTE; dropColumn columnName=VALUE, tableName=REALM_ATTRIBUTE; renameColumn newColumnName=VALUE, oldColumnName=VALUE_NEW, tableName=REALM_ATTRIBUTE		\N	4.23.2	\N	\N	0126422430
14.0.0-KEYCLOAK-11019	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.87614	97	EXECUTED	9:24fb8611e97f29989bea412aa38d12b7	createIndex indexName=IDX_OFFLINE_CSS_PRELOAD, tableName=OFFLINE_CLIENT_SESSION; createIndex indexName=IDX_OFFLINE_USS_BY_USER, tableName=OFFLINE_USER_SESSION; createIndex indexName=IDX_OFFLINE_USS_BY_USERSESS, tableName=OFFLINE_USER_SESSION		\N	4.23.2	\N	\N	0126422430
14.0.0-KEYCLOAK-18286	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.883734	98	MARK_RAN	9:259f89014ce2506ee84740cbf7163aa7	createIndex indexName=IDX_CLIENT_ATT_BY_NAME_VALUE, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
14.0.0-KEYCLOAK-18286-revert	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.894269	99	MARK_RAN	9:04baaf56c116ed19951cbc2cca584022	dropIndex indexName=IDX_CLIENT_ATT_BY_NAME_VALUE, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
14.0.0-KEYCLOAK-18286-supported-dbs	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.91497	100	EXECUTED	9:60ca84a0f8c94ec8c3504a5a3bc88ee8	createIndex indexName=IDX_CLIENT_ATT_BY_NAME_VALUE, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
14.0.0-KEYCLOAK-18286-unsupported-dbs	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.922789	101	MARK_RAN	9:d3d977031d431db16e2c181ce49d73e9	createIndex indexName=IDX_CLIENT_ATT_BY_NAME_VALUE, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
KEYCLOAK-17267-add-index-to-user-attributes	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.944573	102	EXECUTED	9:0b305d8d1277f3a89a0a53a659ad274c	createIndex indexName=IDX_USER_ATTRIBUTE_NAME, tableName=USER_ATTRIBUTE		\N	4.23.2	\N	\N	0126422430
KEYCLOAK-18146-add-saml-art-binding-identifier	keycloak	META-INF/jpa-changelog-14.0.0.xml	2023-11-16 09:20:27.95218	103	EXECUTED	9:2c374ad2cdfe20e2905a84c8fac48460	customChange		\N	4.23.2	\N	\N	0126422430
15.0.0-KEYCLOAK-18467	keycloak	META-INF/jpa-changelog-15.0.0.xml	2023-11-16 09:20:27.965469	104	EXECUTED	9:47a760639ac597360a8219f5b768b4de	addColumn tableName=REALM_LOCALIZATIONS; update tableName=REALM_LOCALIZATIONS; dropColumn columnName=TEXTS, tableName=REALM_LOCALIZATIONS; renameColumn newColumnName=TEXTS, oldColumnName=TEXTS_NEW, tableName=REALM_LOCALIZATIONS; addNotNullConstrai...		\N	4.23.2	\N	\N	0126422430
17.0.0-9562	keycloak	META-INF/jpa-changelog-17.0.0.xml	2023-11-16 09:20:27.984079	105	EXECUTED	9:a6272f0576727dd8cad2522335f5d99e	createIndex indexName=IDX_USER_SERVICE_ACCOUNT, tableName=USER_ENTITY		\N	4.23.2	\N	\N	0126422430
18.0.0-10625-IDX_ADMIN_EVENT_TIME	keycloak	META-INF/jpa-changelog-18.0.0.xml	2023-11-16 09:20:28.001467	106	EXECUTED	9:015479dbd691d9cc8669282f4828c41d	createIndex indexName=IDX_ADMIN_EVENT_TIME, tableName=ADMIN_EVENT_ENTITY		\N	4.23.2	\N	\N	0126422430
19.0.0-10135	keycloak	META-INF/jpa-changelog-19.0.0.xml	2023-11-16 09:20:28.008533	107	EXECUTED	9:9518e495fdd22f78ad6425cc30630221	customChange		\N	4.23.2	\N	\N	0126422430
20.0.0-12964-supported-dbs	keycloak	META-INF/jpa-changelog-20.0.0.xml	2023-11-16 09:20:28.026943	108	EXECUTED	9:e5f243877199fd96bcc842f27a1656ac	createIndex indexName=IDX_GROUP_ATT_BY_NAME_VALUE, tableName=GROUP_ATTRIBUTE		\N	4.23.2	\N	\N	0126422430
20.0.0-12964-unsupported-dbs	keycloak	META-INF/jpa-changelog-20.0.0.xml	2023-11-16 09:20:28.031698	109	MARK_RAN	9:1a6fcaa85e20bdeae0a9ce49b41946a5	createIndex indexName=IDX_GROUP_ATT_BY_NAME_VALUE, tableName=GROUP_ATTRIBUTE		\N	4.23.2	\N	\N	0126422430
client-attributes-string-accomodation-fixed	keycloak	META-INF/jpa-changelog-20.0.0.xml	2023-11-16 09:20:28.044406	110	EXECUTED	9:3f332e13e90739ed0c35b0b25b7822ca	addColumn tableName=CLIENT_ATTRIBUTES; update tableName=CLIENT_ATTRIBUTES; dropColumn columnName=VALUE, tableName=CLIENT_ATTRIBUTES; renameColumn newColumnName=VALUE, oldColumnName=VALUE_NEW, tableName=CLIENT_ATTRIBUTES		\N	4.23.2	\N	\N	0126422430
21.0.2-17277	keycloak	META-INF/jpa-changelog-21.0.2.xml	2023-11-16 09:20:28.052133	111	EXECUTED	9:7ee1f7a3fb8f5588f171fb9a6ab623c0	customChange		\N	4.23.2	\N	\N	0126422430
21.1.0-19404	keycloak	META-INF/jpa-changelog-21.1.0.xml	2023-11-16 09:20:28.144693	112	EXECUTED	9:3d7e830b52f33676b9d64f7f2b2ea634	modifyDataType columnName=DECISION_STRATEGY, tableName=RESOURCE_SERVER_POLICY; modifyDataType columnName=LOGIC, tableName=RESOURCE_SERVER_POLICY; modifyDataType columnName=POLICY_ENFORCE_MODE, tableName=RESOURCE_SERVER		\N	4.23.2	\N	\N	0126422430
21.1.0-19404-2	keycloak	META-INF/jpa-changelog-21.1.0.xml	2023-11-16 09:20:28.150808	113	MARK_RAN	9:627d032e3ef2c06c0e1f73d2ae25c26c	addColumn tableName=RESOURCE_SERVER_POLICY; update tableName=RESOURCE_SERVER_POLICY; dropColumn columnName=DECISION_STRATEGY, tableName=RESOURCE_SERVER_POLICY; renameColumn newColumnName=DECISION_STRATEGY, oldColumnName=DECISION_STRATEGY_NEW, tabl...		\N	4.23.2	\N	\N	0126422430
22.0.0-17484-updated	keycloak	META-INF/jpa-changelog-22.0.0.xml	2023-11-16 09:20:28.159021	114	EXECUTED	9:90af0bfd30cafc17b9f4d6eccd92b8b3	customChange		\N	4.23.2	\N	\N	0126422430
22.0.5-24031	keycloak	META-INF/jpa-changelog-22.0.0.xml	2023-11-16 09:20:28.163726	115	MARK_RAN	9:a60d2d7b315ec2d3eba9e2f145f9df28	customChange		\N	4.23.2	\N	\N	0126422430
\.


--
-- Data for Name: databasechangeloglock; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.databasechangeloglock (id, locked, lockgranted, lockedby) FROM stdin;
1	f	\N	\N
1000	f	\N	\N
1001	f	\N	\N
\.


--
-- Data for Name: default_client_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.default_client_scope (realm_id, scope_id, default_scope) FROM stdin;
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	84fe23bc-e0ef-4406-b069-01f5cb9ea0aa	f
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	fc5549c1-0bd7-42bb-8002-7035958cdeec	t
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	14112e9d-14fa-433d-8ae8-888fbdebe398	t
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	d5c24ac1-3538-467f-b560-a2ff345836bd	t
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	571511e6-0111-405d-b39a-271aefbad4db	f
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4c37fde1-2d9e-4b63-8277-8274622c8bd6	f
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9	t
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	c53e2a13-a31f-4ce0-9560-2e07e67d645b	t
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	349d7526-4813-42e2-abd0-88d762b0784e	f
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	ba412952-1281-4492-89fe-c8cb7e69f6be	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	216afde5-8285-439c-a6ff-109667682532	f
192c7eba-98c5-4d87-9f5f-059ac8515a9f	3bb50451-f5b6-470c-b9ef-f56947982bce	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	29874bd4-37d5-4d8e-a70d-35fac7b7316f	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	b633de75-729d-421f-afe5-06381d531a7d	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	322bb55b-9c86-405c-bc4b-4e95d1f9f020	f
192c7eba-98c5-4d87-9f5f-059ac8515a9f	bac6e34a-8ddc-456e-ada2-65c62aa4eac9	f
192c7eba-98c5-4d87-9f5f-059ac8515a9f	bc4cb0cb-9821-4678-b147-caebf705b629	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	b276f043-6971-4544-968d-45b83a8fd024	t
192c7eba-98c5-4d87-9f5f-059ac8515a9f	43a600c5-7c41-4436-b3f4-8c6a1b066348	f
192c7eba-98c5-4d87-9f5f-059ac8515a9f	40669fe7-d52a-4039-8da6-bf09ce2f1907	t
\.


--
-- Data for Name: event_entity; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.event_entity (id, client_id, details_json, error, ip_address, realm_id, session_id, event_time, type, user_id) FROM stdin;
\.


--
-- Data for Name: fed_user_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_attribute (id, name, user_id, realm_id, storage_provider_id, value) FROM stdin;
\.


--
-- Data for Name: fed_user_consent; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_consent (id, client_id, user_id, realm_id, storage_provider_id, created_date, last_updated_date, client_storage_provider, external_client_id) FROM stdin;
\.


--
-- Data for Name: fed_user_consent_cl_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_consent_cl_scope (user_consent_id, scope_id) FROM stdin;
\.


--
-- Data for Name: fed_user_credential; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_credential (id, salt, type, created_date, user_id, realm_id, storage_provider_id, user_label, secret_data, credential_data, priority) FROM stdin;
\.


--
-- Data for Name: fed_user_group_membership; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_group_membership (group_id, user_id, realm_id, storage_provider_id) FROM stdin;
\.


--
-- Data for Name: fed_user_required_action; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_required_action (required_action, user_id, realm_id, storage_provider_id) FROM stdin;
\.


--
-- Data for Name: fed_user_role_mapping; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.fed_user_role_mapping (role_id, user_id, realm_id, storage_provider_id) FROM stdin;
\.


--
-- Data for Name: federated_identity; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.federated_identity (identity_provider, realm_id, federated_user_id, federated_username, token, user_id) FROM stdin;
\.


--
-- Data for Name: federated_user; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.federated_user (id, storage_provider_id, realm_id) FROM stdin;
\.


--
-- Data for Name: group_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.group_attribute (id, name, value, group_id) FROM stdin;
\.


--
-- Data for Name: group_role_mapping; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.group_role_mapping (role_id, group_id) FROM stdin;
\.


--
-- Data for Name: identity_provider; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.identity_provider (internal_id, enabled, provider_alias, provider_id, store_token, authenticate_by_default, realm_id, add_token_role, trust_email, first_broker_login_flow_id, post_broker_login_flow_id, provider_display_name, link_only) FROM stdin;
\.


--
-- Data for Name: identity_provider_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.identity_provider_config (identity_provider_id, value, name) FROM stdin;
\.


--
-- Data for Name: identity_provider_mapper; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.identity_provider_mapper (id, name, idp_alias, idp_mapper_name, realm_id) FROM stdin;
\.


--
-- Data for Name: idp_mapper_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.idp_mapper_config (idp_mapper_id, value, name) FROM stdin;
\.


--
-- Data for Name: keycloak_group; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.keycloak_group (id, name, parent_group, realm_id) FROM stdin;
\.


--
-- Data for Name: keycloak_role; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.keycloak_role (id, client_realm_constraint, client_role, description, name, realm_id, client, realm) FROM stdin;
9248d8ff-8fdf-483f-911c-b400a4715be0	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	${role_default-roles}	default-roles-master	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	\N
db244a85-417d-4a00-a896-e9312fe77119	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	${role_admin}	admin	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	\N
f878f2f8-582f-403d-90fa-b27afc636d22	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	${role_create-realm}	create-realm	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	\N
ee0717c8-8bca-4a22-acef-b11ebecfbe36	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_create-client}	create-client	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
cdc006d9-0d5f-450e-a789-b0302f9bcb76	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-realm}	view-realm	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
b3e7619b-0cc3-4203-95ef-04d93e17418d	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-users}	view-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
eac59232-b35c-4a86-9ac1-8a45661a8ffb	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-clients}	view-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
e91628e6-caf5-4bd1-a456-5439d92697ec	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-events}	view-events	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
c589cc50-9f0d-4074-8503-f43030e973d3	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-identity-providers}	view-identity-providers	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
be042b2d-74cf-4ead-a59b-d0f570d99d82	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_view-authorization}	view-authorization	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
7e6afcd8-f918-40c3-b931-d37111136cf6	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-realm}	manage-realm	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
5da77801-c20e-4b3d-8e75-7431f862db7c	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-users}	manage-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
d80ba2ad-3b0d-4c03-afa7-bb5478aba1e1	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-clients}	manage-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
dc12ae77-f398-4558-a395-9c991984f44e	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-events}	manage-events	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
9fdaa1fc-3bcd-4f74-9bf5-f887bfc53303	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-identity-providers}	manage-identity-providers	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
cecf20d1-a0c4-4d7f-a34f-3a4dbfec6a33	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_manage-authorization}	manage-authorization	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
040c5a23-b2bf-47fa-a4b0-751797c519bc	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_query-users}	query-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
3a63f54b-72be-48c3-a72b-64abec570d55	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_query-clients}	query-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
98bf02e9-40b4-4782-8615-9e91391b5643	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_query-realms}	query-realms	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
d140eaa3-71b1-4106-a950-7109e50a1c6c	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_query-groups}	query-groups	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
249cb71e-51c3-4aa6-bbc7-160541653b0b	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_view-profile}	view-profile	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
407b7326-22e9-47de-b32c-f34bdbb48bf6	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_manage-account}	manage-account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
10c09cfc-fe8e-435a-868f-905bab146edc	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_manage-account-links}	manage-account-links	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
436d44fd-5ec7-47c9-b0f3-5eb0b86758a1	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_view-applications}	view-applications	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
d9265bc5-9663-43c3-b1b7-72eea1c20ae7	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_view-consent}	view-consent	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
45b5847d-0e9f-4722-accd-bc48521a63ab	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_manage-consent}	manage-consent	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
90bca2e3-0ed3-4f76-8f67-2bf563be2472	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_view-groups}	view-groups	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
04f76054-89bc-4f88-8a30-ccc905f38596	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	t	${role_delete-account}	delete-account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	aa04ecbf-e4d0-49ce-a733-ffc6e4309498	\N
93e6ca92-c5d3-4e20-8472-bd560aed2872	61987548-33ab-4959-9fd7-9b3bc2cb3e79	t	${role_read-token}	read-token	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	61987548-33ab-4959-9fd7-9b3bc2cb3e79	\N
a4a196af-5eae-4719-9d55-8e4dabb27a99	7054aec7-dafe-46ea-b752-855f1626b97a	t	${role_impersonation}	impersonation	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	7054aec7-dafe-46ea-b752-855f1626b97a	\N
c16af2bf-5d84-40f4-8b6f-09875cbde07a	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	${role_offline-access}	offline_access	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	\N
4ad28e4c-c998-496c-8418-fbaac75767d9	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	${role_uma_authorization}	uma_authorization	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	\N	\N
355d504e-2e39-4d69-b225-04074afc8263	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f	${role_default-roles}	default-roles-logprep	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N	\N
dd1dc591-25eb-41b0-ad9b-6626f578f3f9	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_create-client}	create-client	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
ef70fd57-bb4d-433d-87ce-b207be534105	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-realm}	view-realm	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
223a8341-34d4-4c4d-be7f-105ec6730c6d	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-users}	view-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
8eb82050-5e5c-4a00-b1f7-92a64f1bd403	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-clients}	view-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
a2c38582-004b-4821-92cf-c9aced935469	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-events}	view-events	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
4b283bf4-f313-447b-bd3d-fc2c612fc7bd	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-identity-providers}	view-identity-providers	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
433a40d5-9dbe-4114-ba89-187ef4a67b68	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_view-authorization}	view-authorization	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
85379951-fff1-4821-8184-d027116bffb5	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-realm}	manage-realm	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
b571f6a9-717c-4cf0-baed-e07c558d5976	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-users}	manage-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
2e33949b-0165-455a-a342-71062e369bb0	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-clients}	manage-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
527489de-7576-4991-a629-3fb0c5604255	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-events}	manage-events	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
febfa69b-d5f3-4c43-9274-081338c35dba	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-identity-providers}	manage-identity-providers	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
14e594eb-c427-49c1-8201-593c2d6cbe17	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_manage-authorization}	manage-authorization	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
f64ea7a4-7f40-4516-a3ce-f388fe482394	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_query-users}	query-users	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
abd4c968-9e27-47cf-80ab-0e4e0af854f9	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_query-clients}	query-clients	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
164141e7-7f8e-41a4-a464-c13711bdc55a	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_query-realms}	query-realms	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
ad01d462-d24f-40af-a80b-46688d4100e6	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_query-groups}	query-groups	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
f9be7c14-1996-469a-8c08-b92068aff63d	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_realm-admin}	realm-admin	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
7c8bbec1-20c7-4fbf-b002-69b81a7e16ab	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_create-client}	create-client	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
588cdf08-d847-4d93-bca5-a648ce7173ac	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-realm}	view-realm	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
ef1ea854-a8bf-4ae7-9ff8-b43034e18c7f	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-users}	view-users	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
74f4a81a-a120-477c-962d-3148529ff9b3	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-clients}	view-clients	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
21dc671d-d4f2-4698-887a-390353d575d7	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-events}	view-events	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
6f91aef4-6e10-454e-bb22-b05bdab44ede	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-identity-providers}	view-identity-providers	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
bc3af619-5c23-46da-b563-39303ffa4a10	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_view-authorization}	view-authorization	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
3fb93172-19ae-4ea9-a2b6-b594c1d7aaf1	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-realm}	manage-realm	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
2635161f-d630-438f-a126-9d37f998be53	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-users}	manage-users	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
b2b78255-c74f-4849-9ff0-ca0eac64459d	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-clients}	manage-clients	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
c2976451-ff24-414a-a890-14458eca13ca	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-events}	manage-events	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
1ea12752-aebb-4adb-a1e7-f63ff8d80d9d	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-identity-providers}	manage-identity-providers	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
8b4b3d57-cf63-4cc3-a5f8-f20ec3b967b9	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_manage-authorization}	manage-authorization	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
c1720889-b5be-4348-93f1-513b3f449b8b	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_query-users}	query-users	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
c2572cfd-5df4-4375-8719-03f0530e921b	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_query-clients}	query-clients	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
326d4ec9-7301-406e-be3e-dfeb4e1d4c38	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_query-realms}	query-realms	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
bd29f472-7875-4521-878d-49f6b1acca06	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_query-groups}	query-groups	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
34d36fab-24e6-4bfe-a88d-21e87a12ecc3	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_view-profile}	view-profile	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
0c0d6eb7-a699-4100-82b3-f0d6b94cfb10	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_manage-account}	manage-account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
670ae089-cd79-400c-852b-51d422e00d01	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_manage-account-links}	manage-account-links	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
001e2f51-1828-4daf-94e4-018e1517bbcc	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_view-applications}	view-applications	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
c8001fee-9758-482c-a67c-8760461f710b	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_view-consent}	view-consent	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
6dde7388-89d2-4ad3-8717-a816d9904233	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_manage-consent}	manage-consent	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
320155b6-942b-4ab0-ae10-20d67b187b7a	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_view-groups}	view-groups	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
b8eaa88b-4555-4c26-9672-6db3e9f7cd75	713208be-0b29-4727-abc0-1c5102bf0c0e	t	${role_delete-account}	delete-account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	713208be-0b29-4727-abc0-1c5102bf0c0e	\N
758319a2-c266-48a2-9f70-e6672c75fd8e	4528294a-48c5-4295-ba48-015c67ad0632	t	${role_impersonation}	impersonation	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	4528294a-48c5-4295-ba48-015c67ad0632	\N
922ddad7-5850-4972-98ec-c4ea84623b24	91109a48-1062-4ca1-a7e6-b511be738faa	t	${role_impersonation}	impersonation	192c7eba-98c5-4d87-9f5f-059ac8515a9f	91109a48-1062-4ca1-a7e6-b511be738faa	\N
dc419da1-a5cd-42e1-b4f0-5942c20ac435	26ef3d61-6c70-487b-b633-c7f798f0f4a5	t	${role_read-token}	read-token	192c7eba-98c5-4d87-9f5f-059ac8515a9f	26ef3d61-6c70-487b-b633-c7f798f0f4a5	\N
f70e4815-0644-49cc-8ea9-c6c87c4afb55	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f	${role_offline-access}	offline_access	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N	\N
d6cd7fe1-ed88-4175-ac9c-7dfc0729f732	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f	${role_uma_authorization}	uma_authorization	192c7eba-98c5-4d87-9f5f-059ac8515a9f	\N	\N
c580e950-e410-4bf8-a94a-c42c3193c4f1	02d1898e-b586-4795-b3ff-fd2bae926af0	t		fda-admin	192c7eba-98c5-4d87-9f5f-059ac8515a9f	02d1898e-b586-4795-b3ff-fd2bae926af0	\N
\.


--
-- Data for Name: migration_model; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.migration_model (id, version, update_time) FROM stdin;
61qb1	22.0.5	1700126428
\.


--
-- Data for Name: offline_client_session; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.offline_client_session (user_session_id, client_id, offline_flag, "timestamp", data, client_storage_provider, external_client_id) FROM stdin;
\.


--
-- Data for Name: offline_user_session; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.offline_user_session (user_session_id, user_id, realm_id, created_on, offline_flag, data, last_session_refresh) FROM stdin;
\.


--
-- Data for Name: policy_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.policy_config (policy_id, name, value) FROM stdin;
\.


--
-- Data for Name: protocol_mapper; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.protocol_mapper (id, name, protocol, protocol_mapper_name, client_id, client_scope_id) FROM stdin;
4b52cc7d-4498-4766-aa2d-dd936dc6d444	audience resolve	openid-connect	oidc-audience-resolve-mapper	b42513aa-047e-4187-9fd7-7ce4137e3206	\N
f436ea7c-3c4c-4e10-a7bb-45f34167b018	locale	openid-connect	oidc-usermodel-attribute-mapper	ffa621f0-3e6c-477d-86da-eb2186eb1f40	\N
a4e4ae30-784a-467a-909f-351eabaf5042	role list	saml	saml-role-list-mapper	\N	fc5549c1-0bd7-42bb-8002-7035958cdeec
7c2de081-81c3-4e05-8211-0e48be86aa0f	full name	openid-connect	oidc-full-name-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
4b193d04-8106-4b8b-a671-bc84f517da10	family name	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	given name	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	middle name	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
9999b8af-220c-4218-ad32-e0b466c1177d	nickname	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
39c81953-846d-4286-a6a4-4addf2706bc3	username	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
044c02ac-ac50-42cb-9664-4acf0a03ede1	profile	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
082c8b5c-4755-4ace-9327-0fdb9de80f27	picture	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	website	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	gender	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
d799f82f-b72d-4fed-8eca-03a71312b4be	birthdate	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
389881b8-d33b-4f17-bbcb-427739f34733	zoneinfo	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
de9bbff0-54bd-4c53-b0f1-d025fc74966a	locale	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
1badfe65-899f-4069-90bf-8e3fdb3bec12	updated at	openid-connect	oidc-usermodel-attribute-mapper	\N	14112e9d-14fa-433d-8ae8-888fbdebe398
ae2af587-23d0-4f32-a531-70e39bd7ffe4	email	openid-connect	oidc-usermodel-attribute-mapper	\N	d5c24ac1-3538-467f-b560-a2ff345836bd
71387367-5c68-4072-87c1-90dd9cedcf26	email verified	openid-connect	oidc-usermodel-property-mapper	\N	d5c24ac1-3538-467f-b560-a2ff345836bd
c7cead05-e2df-499a-86fc-603500a98786	address	openid-connect	oidc-address-mapper	\N	571511e6-0111-405d-b39a-271aefbad4db
b038926a-9741-4336-9b6b-c6d05374b5e8	phone number	openid-connect	oidc-usermodel-attribute-mapper	\N	4c37fde1-2d9e-4b63-8277-8274622c8bd6
f0378773-1e44-40ce-8861-640f91e5a510	phone number verified	openid-connect	oidc-usermodel-attribute-mapper	\N	4c37fde1-2d9e-4b63-8277-8274622c8bd6
71b9875e-9dfc-479b-8862-92440a0be4e6	realm roles	openid-connect	oidc-usermodel-realm-role-mapper	\N	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	client roles	openid-connect	oidc-usermodel-client-role-mapper	\N	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9
dd3cf866-9db8-4217-bc57-5f5effa24360	audience resolve	openid-connect	oidc-audience-resolve-mapper	\N	bec44fc1-53d4-4ed6-9460-904dc6a3aaa9
87315497-023f-4c4e-86cc-9349f6a35369	allowed web origins	openid-connect	oidc-allowed-origins-mapper	\N	c53e2a13-a31f-4ce0-9560-2e07e67d645b
685a95ec-fd78-47c3-b0f2-dbd873b77adb	upn	openid-connect	oidc-usermodel-attribute-mapper	\N	349d7526-4813-42e2-abd0-88d762b0784e
84ca2584-4c9b-4b65-b168-1b754cc5f62a	groups	openid-connect	oidc-usermodel-realm-role-mapper	\N	349d7526-4813-42e2-abd0-88d762b0784e
642ae0a2-d872-47fb-a46e-8aa0955a88cc	acr loa level	openid-connect	oidc-acr-mapper	\N	ba412952-1281-4492-89fe-c8cb7e69f6be
72352210-7c28-4a53-a01b-05cce6a03a6d	audience resolve	openid-connect	oidc-audience-resolve-mapper	89b2e0d2-5fb6-4bfb-82d0-c368080d2663	\N
89573f1b-ca2b-4c47-a38d-b4a8d81819ad	role list	saml	saml-role-list-mapper	\N	3bb50451-f5b6-470c-b9ef-f56947982bce
5f92ed9a-4b7b-4889-a7d0-bb3cb9439d91	full name	openid-connect	oidc-full-name-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
824e2d4e-dadd-430d-9685-1bf2acec450d	family name	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	given name	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
e8aa29c9-61df-41c6-a516-2a50dd130c10	middle name	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
36b9ff79-40b2-4184-9fd6-b31669a28657	nickname	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	username	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
50e66a1c-1e6f-497d-ae73-5572859e558d	profile	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
864362f5-8557-40cf-aa1c-714344a33536	picture	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
3c8f4650-5aa8-458b-a7a2-5e283802c842	website	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	gender	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	birthdate	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
38c01846-f75c-4079-927f-636df306d10c	zoneinfo	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
c51c3bc1-042b-430a-8c5b-0542f7033a98	locale	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
08f082ac-d66f-46ac-b5ad-cba0ab750655	updated at	openid-connect	oidc-usermodel-attribute-mapper	\N	29874bd4-37d5-4d8e-a70d-35fac7b7316f
99bd500c-db8d-477c-9d7d-3b0459e0041f	email	openid-connect	oidc-usermodel-attribute-mapper	\N	b633de75-729d-421f-afe5-06381d531a7d
b1879cb5-59fe-4267-ace2-9bb16033bce7	email verified	openid-connect	oidc-usermodel-property-mapper	\N	b633de75-729d-421f-afe5-06381d531a7d
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	address	openid-connect	oidc-address-mapper	\N	322bb55b-9c86-405c-bc4b-4e95d1f9f020
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	phone number	openid-connect	oidc-usermodel-attribute-mapper	\N	bac6e34a-8ddc-456e-ada2-65c62aa4eac9
983425fc-0582-48cb-a74f-3d84c4b58586	phone number verified	openid-connect	oidc-usermodel-attribute-mapper	\N	bac6e34a-8ddc-456e-ada2-65c62aa4eac9
0168cd70-f7a1-4406-b2de-15c9b11bb80b	realm roles	openid-connect	oidc-usermodel-realm-role-mapper	\N	bc4cb0cb-9821-4678-b147-caebf705b629
b9270ced-976e-45b6-9dac-147a84f28914	client roles	openid-connect	oidc-usermodel-client-role-mapper	\N	bc4cb0cb-9821-4678-b147-caebf705b629
8d601e01-de88-443f-8f80-d82019896ccf	audience resolve	openid-connect	oidc-audience-resolve-mapper	\N	bc4cb0cb-9821-4678-b147-caebf705b629
ef9644d9-bd26-4bee-909c-9070b7ebc3f7	allowed web origins	openid-connect	oidc-allowed-origins-mapper	\N	b276f043-6971-4544-968d-45b83a8fd024
a20df460-17fa-436e-835f-ca46ef7e5058	upn	openid-connect	oidc-usermodel-attribute-mapper	\N	43a600c5-7c41-4436-b3f4-8c6a1b066348
c01bc375-b5f9-4936-8251-7c7be8a94b04	groups	openid-connect	oidc-usermodel-realm-role-mapper	\N	43a600c5-7c41-4436-b3f4-8c6a1b066348
4258a352-b86a-4c06-91eb-51e3c06330fe	acr loa level	openid-connect	oidc-acr-mapper	\N	40669fe7-d52a-4039-8da6-bf09ce2f1907
8f898d62-602a-4868-a30c-a583fc40b5f1	locale	openid-connect	oidc-usermodel-attribute-mapper	6a67af5f-f536-4211-8f84-d0fcd5c0bccf	\N
\.


--
-- Data for Name: protocol_mapper_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.protocol_mapper_config (protocol_mapper_id, value, name) FROM stdin;
f436ea7c-3c4c-4e10-a7bb-45f34167b018	true	userinfo.token.claim
f436ea7c-3c4c-4e10-a7bb-45f34167b018	locale	user.attribute
f436ea7c-3c4c-4e10-a7bb-45f34167b018	true	id.token.claim
f436ea7c-3c4c-4e10-a7bb-45f34167b018	true	access.token.claim
f436ea7c-3c4c-4e10-a7bb-45f34167b018	locale	claim.name
f436ea7c-3c4c-4e10-a7bb-45f34167b018	String	jsonType.label
a4e4ae30-784a-467a-909f-351eabaf5042	false	single
a4e4ae30-784a-467a-909f-351eabaf5042	Basic	attribute.nameformat
a4e4ae30-784a-467a-909f-351eabaf5042	Role	attribute.name
044c02ac-ac50-42cb-9664-4acf0a03ede1	true	userinfo.token.claim
044c02ac-ac50-42cb-9664-4acf0a03ede1	profile	user.attribute
044c02ac-ac50-42cb-9664-4acf0a03ede1	true	id.token.claim
044c02ac-ac50-42cb-9664-4acf0a03ede1	true	access.token.claim
044c02ac-ac50-42cb-9664-4acf0a03ede1	profile	claim.name
044c02ac-ac50-42cb-9664-4acf0a03ede1	String	jsonType.label
082c8b5c-4755-4ace-9327-0fdb9de80f27	true	userinfo.token.claim
082c8b5c-4755-4ace-9327-0fdb9de80f27	picture	user.attribute
082c8b5c-4755-4ace-9327-0fdb9de80f27	true	id.token.claim
082c8b5c-4755-4ace-9327-0fdb9de80f27	true	access.token.claim
082c8b5c-4755-4ace-9327-0fdb9de80f27	picture	claim.name
082c8b5c-4755-4ace-9327-0fdb9de80f27	String	jsonType.label
1badfe65-899f-4069-90bf-8e3fdb3bec12	true	userinfo.token.claim
1badfe65-899f-4069-90bf-8e3fdb3bec12	updatedAt	user.attribute
1badfe65-899f-4069-90bf-8e3fdb3bec12	true	id.token.claim
1badfe65-899f-4069-90bf-8e3fdb3bec12	true	access.token.claim
1badfe65-899f-4069-90bf-8e3fdb3bec12	updated_at	claim.name
1badfe65-899f-4069-90bf-8e3fdb3bec12	long	jsonType.label
389881b8-d33b-4f17-bbcb-427739f34733	true	userinfo.token.claim
389881b8-d33b-4f17-bbcb-427739f34733	zoneinfo	user.attribute
389881b8-d33b-4f17-bbcb-427739f34733	true	id.token.claim
389881b8-d33b-4f17-bbcb-427739f34733	true	access.token.claim
389881b8-d33b-4f17-bbcb-427739f34733	zoneinfo	claim.name
389881b8-d33b-4f17-bbcb-427739f34733	String	jsonType.label
39c81953-846d-4286-a6a4-4addf2706bc3	true	userinfo.token.claim
39c81953-846d-4286-a6a4-4addf2706bc3	username	user.attribute
39c81953-846d-4286-a6a4-4addf2706bc3	true	id.token.claim
39c81953-846d-4286-a6a4-4addf2706bc3	true	access.token.claim
39c81953-846d-4286-a6a4-4addf2706bc3	preferred_username	claim.name
39c81953-846d-4286-a6a4-4addf2706bc3	String	jsonType.label
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	true	userinfo.token.claim
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	gender	user.attribute
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	true	id.token.claim
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	true	access.token.claim
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	gender	claim.name
4457bcc1-9353-4dcb-b4aa-360abcbcfccb	String	jsonType.label
4b193d04-8106-4b8b-a671-bc84f517da10	true	userinfo.token.claim
4b193d04-8106-4b8b-a671-bc84f517da10	lastName	user.attribute
4b193d04-8106-4b8b-a671-bc84f517da10	true	id.token.claim
4b193d04-8106-4b8b-a671-bc84f517da10	true	access.token.claim
4b193d04-8106-4b8b-a671-bc84f517da10	family_name	claim.name
4b193d04-8106-4b8b-a671-bc84f517da10	String	jsonType.label
7c2de081-81c3-4e05-8211-0e48be86aa0f	true	userinfo.token.claim
7c2de081-81c3-4e05-8211-0e48be86aa0f	true	id.token.claim
7c2de081-81c3-4e05-8211-0e48be86aa0f	true	access.token.claim
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	true	userinfo.token.claim
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	website	user.attribute
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	true	id.token.claim
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	true	access.token.claim
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	website	claim.name
92b9d6d4-716f-41b8-ad6f-fa96252a5a64	String	jsonType.label
9999b8af-220c-4218-ad32-e0b466c1177d	true	userinfo.token.claim
9999b8af-220c-4218-ad32-e0b466c1177d	nickname	user.attribute
9999b8af-220c-4218-ad32-e0b466c1177d	true	id.token.claim
9999b8af-220c-4218-ad32-e0b466c1177d	true	access.token.claim
9999b8af-220c-4218-ad32-e0b466c1177d	nickname	claim.name
9999b8af-220c-4218-ad32-e0b466c1177d	String	jsonType.label
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	true	userinfo.token.claim
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	firstName	user.attribute
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	true	id.token.claim
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	true	access.token.claim
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	given_name	claim.name
b11dd5c8-5a75-4e29-8a0e-53104cd5f4b1	String	jsonType.label
d799f82f-b72d-4fed-8eca-03a71312b4be	true	userinfo.token.claim
d799f82f-b72d-4fed-8eca-03a71312b4be	birthdate	user.attribute
d799f82f-b72d-4fed-8eca-03a71312b4be	true	id.token.claim
d799f82f-b72d-4fed-8eca-03a71312b4be	true	access.token.claim
d799f82f-b72d-4fed-8eca-03a71312b4be	birthdate	claim.name
d799f82f-b72d-4fed-8eca-03a71312b4be	String	jsonType.label
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	true	userinfo.token.claim
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	middleName	user.attribute
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	true	id.token.claim
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	true	access.token.claim
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	middle_name	claim.name
dc54c995-af7f-450e-9dd9-d9f88e6a58ba	String	jsonType.label
de9bbff0-54bd-4c53-b0f1-d025fc74966a	true	userinfo.token.claim
de9bbff0-54bd-4c53-b0f1-d025fc74966a	locale	user.attribute
de9bbff0-54bd-4c53-b0f1-d025fc74966a	true	id.token.claim
de9bbff0-54bd-4c53-b0f1-d025fc74966a	true	access.token.claim
de9bbff0-54bd-4c53-b0f1-d025fc74966a	locale	claim.name
de9bbff0-54bd-4c53-b0f1-d025fc74966a	String	jsonType.label
71387367-5c68-4072-87c1-90dd9cedcf26	true	userinfo.token.claim
71387367-5c68-4072-87c1-90dd9cedcf26	emailVerified	user.attribute
71387367-5c68-4072-87c1-90dd9cedcf26	true	id.token.claim
71387367-5c68-4072-87c1-90dd9cedcf26	true	access.token.claim
71387367-5c68-4072-87c1-90dd9cedcf26	email_verified	claim.name
71387367-5c68-4072-87c1-90dd9cedcf26	boolean	jsonType.label
ae2af587-23d0-4f32-a531-70e39bd7ffe4	true	userinfo.token.claim
ae2af587-23d0-4f32-a531-70e39bd7ffe4	email	user.attribute
ae2af587-23d0-4f32-a531-70e39bd7ffe4	true	id.token.claim
ae2af587-23d0-4f32-a531-70e39bd7ffe4	true	access.token.claim
ae2af587-23d0-4f32-a531-70e39bd7ffe4	email	claim.name
ae2af587-23d0-4f32-a531-70e39bd7ffe4	String	jsonType.label
c7cead05-e2df-499a-86fc-603500a98786	formatted	user.attribute.formatted
c7cead05-e2df-499a-86fc-603500a98786	country	user.attribute.country
c7cead05-e2df-499a-86fc-603500a98786	postal_code	user.attribute.postal_code
c7cead05-e2df-499a-86fc-603500a98786	true	userinfo.token.claim
c7cead05-e2df-499a-86fc-603500a98786	street	user.attribute.street
c7cead05-e2df-499a-86fc-603500a98786	true	id.token.claim
c7cead05-e2df-499a-86fc-603500a98786	region	user.attribute.region
c7cead05-e2df-499a-86fc-603500a98786	true	access.token.claim
c7cead05-e2df-499a-86fc-603500a98786	locality	user.attribute.locality
b038926a-9741-4336-9b6b-c6d05374b5e8	true	userinfo.token.claim
b038926a-9741-4336-9b6b-c6d05374b5e8	phoneNumber	user.attribute
b038926a-9741-4336-9b6b-c6d05374b5e8	true	id.token.claim
b038926a-9741-4336-9b6b-c6d05374b5e8	true	access.token.claim
b038926a-9741-4336-9b6b-c6d05374b5e8	phone_number	claim.name
b038926a-9741-4336-9b6b-c6d05374b5e8	String	jsonType.label
f0378773-1e44-40ce-8861-640f91e5a510	true	userinfo.token.claim
f0378773-1e44-40ce-8861-640f91e5a510	phoneNumberVerified	user.attribute
f0378773-1e44-40ce-8861-640f91e5a510	true	id.token.claim
f0378773-1e44-40ce-8861-640f91e5a510	true	access.token.claim
f0378773-1e44-40ce-8861-640f91e5a510	phone_number_verified	claim.name
f0378773-1e44-40ce-8861-640f91e5a510	boolean	jsonType.label
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	true	multivalued
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	foo	user.attribute
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	true	access.token.claim
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	resource_access.${client_id}.roles	claim.name
3c33bc4d-3a69-4d82-aa43-ccf31f6ec246	String	jsonType.label
71b9875e-9dfc-479b-8862-92440a0be4e6	true	multivalued
71b9875e-9dfc-479b-8862-92440a0be4e6	foo	user.attribute
71b9875e-9dfc-479b-8862-92440a0be4e6	true	access.token.claim
71b9875e-9dfc-479b-8862-92440a0be4e6	realm_access.roles	claim.name
71b9875e-9dfc-479b-8862-92440a0be4e6	String	jsonType.label
685a95ec-fd78-47c3-b0f2-dbd873b77adb	true	userinfo.token.claim
685a95ec-fd78-47c3-b0f2-dbd873b77adb	username	user.attribute
685a95ec-fd78-47c3-b0f2-dbd873b77adb	true	id.token.claim
685a95ec-fd78-47c3-b0f2-dbd873b77adb	true	access.token.claim
685a95ec-fd78-47c3-b0f2-dbd873b77adb	upn	claim.name
685a95ec-fd78-47c3-b0f2-dbd873b77adb	String	jsonType.label
84ca2584-4c9b-4b65-b168-1b754cc5f62a	true	multivalued
84ca2584-4c9b-4b65-b168-1b754cc5f62a	foo	user.attribute
84ca2584-4c9b-4b65-b168-1b754cc5f62a	true	id.token.claim
84ca2584-4c9b-4b65-b168-1b754cc5f62a	true	access.token.claim
84ca2584-4c9b-4b65-b168-1b754cc5f62a	groups	claim.name
84ca2584-4c9b-4b65-b168-1b754cc5f62a	String	jsonType.label
642ae0a2-d872-47fb-a46e-8aa0955a88cc	true	id.token.claim
642ae0a2-d872-47fb-a46e-8aa0955a88cc	true	access.token.claim
89573f1b-ca2b-4c47-a38d-b4a8d81819ad	false	single
89573f1b-ca2b-4c47-a38d-b4a8d81819ad	Basic	attribute.nameformat
89573f1b-ca2b-4c47-a38d-b4a8d81819ad	Role	attribute.name
08f082ac-d66f-46ac-b5ad-cba0ab750655	true	userinfo.token.claim
08f082ac-d66f-46ac-b5ad-cba0ab750655	updatedAt	user.attribute
08f082ac-d66f-46ac-b5ad-cba0ab750655	true	id.token.claim
08f082ac-d66f-46ac-b5ad-cba0ab750655	true	access.token.claim
08f082ac-d66f-46ac-b5ad-cba0ab750655	updated_at	claim.name
08f082ac-d66f-46ac-b5ad-cba0ab750655	long	jsonType.label
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	true	userinfo.token.claim
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	firstName	user.attribute
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	true	id.token.claim
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	true	access.token.claim
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	given_name	claim.name
1125f2a9-e32a-4aa6-a680-7dd2a2ff1b54	String	jsonType.label
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	true	userinfo.token.claim
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	gender	user.attribute
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	true	id.token.claim
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	true	access.token.claim
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	gender	claim.name
1c72ab66-18a8-4b12-81a8-948ec8bfcb3a	String	jsonType.label
36b9ff79-40b2-4184-9fd6-b31669a28657	true	userinfo.token.claim
36b9ff79-40b2-4184-9fd6-b31669a28657	nickname	user.attribute
36b9ff79-40b2-4184-9fd6-b31669a28657	true	id.token.claim
36b9ff79-40b2-4184-9fd6-b31669a28657	true	access.token.claim
36b9ff79-40b2-4184-9fd6-b31669a28657	nickname	claim.name
36b9ff79-40b2-4184-9fd6-b31669a28657	String	jsonType.label
38c01846-f75c-4079-927f-636df306d10c	true	userinfo.token.claim
38c01846-f75c-4079-927f-636df306d10c	zoneinfo	user.attribute
38c01846-f75c-4079-927f-636df306d10c	true	id.token.claim
38c01846-f75c-4079-927f-636df306d10c	true	access.token.claim
38c01846-f75c-4079-927f-636df306d10c	zoneinfo	claim.name
38c01846-f75c-4079-927f-636df306d10c	String	jsonType.label
3c8f4650-5aa8-458b-a7a2-5e283802c842	true	userinfo.token.claim
3c8f4650-5aa8-458b-a7a2-5e283802c842	website	user.attribute
3c8f4650-5aa8-458b-a7a2-5e283802c842	true	id.token.claim
3c8f4650-5aa8-458b-a7a2-5e283802c842	true	access.token.claim
3c8f4650-5aa8-458b-a7a2-5e283802c842	website	claim.name
3c8f4650-5aa8-458b-a7a2-5e283802c842	String	jsonType.label
50e66a1c-1e6f-497d-ae73-5572859e558d	true	userinfo.token.claim
50e66a1c-1e6f-497d-ae73-5572859e558d	profile	user.attribute
50e66a1c-1e6f-497d-ae73-5572859e558d	true	id.token.claim
50e66a1c-1e6f-497d-ae73-5572859e558d	true	access.token.claim
50e66a1c-1e6f-497d-ae73-5572859e558d	profile	claim.name
50e66a1c-1e6f-497d-ae73-5572859e558d	String	jsonType.label
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	true	userinfo.token.claim
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	username	user.attribute
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	true	id.token.claim
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	true	access.token.claim
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	preferred_username	claim.name
598c444a-8a5b-4d1b-b9bc-0ee1a2a209d2	String	jsonType.label
5f92ed9a-4b7b-4889-a7d0-bb3cb9439d91	true	userinfo.token.claim
5f92ed9a-4b7b-4889-a7d0-bb3cb9439d91	true	id.token.claim
5f92ed9a-4b7b-4889-a7d0-bb3cb9439d91	true	access.token.claim
824e2d4e-dadd-430d-9685-1bf2acec450d	true	userinfo.token.claim
824e2d4e-dadd-430d-9685-1bf2acec450d	lastName	user.attribute
824e2d4e-dadd-430d-9685-1bf2acec450d	true	id.token.claim
824e2d4e-dadd-430d-9685-1bf2acec450d	true	access.token.claim
824e2d4e-dadd-430d-9685-1bf2acec450d	family_name	claim.name
824e2d4e-dadd-430d-9685-1bf2acec450d	String	jsonType.label
864362f5-8557-40cf-aa1c-714344a33536	true	userinfo.token.claim
864362f5-8557-40cf-aa1c-714344a33536	picture	user.attribute
864362f5-8557-40cf-aa1c-714344a33536	true	id.token.claim
864362f5-8557-40cf-aa1c-714344a33536	true	access.token.claim
864362f5-8557-40cf-aa1c-714344a33536	picture	claim.name
864362f5-8557-40cf-aa1c-714344a33536	String	jsonType.label
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	true	userinfo.token.claim
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	birthdate	user.attribute
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	true	id.token.claim
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	true	access.token.claim
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	birthdate	claim.name
b1c2a5fe-0def-4a2c-9b8a-713be82a9775	String	jsonType.label
c51c3bc1-042b-430a-8c5b-0542f7033a98	true	userinfo.token.claim
c51c3bc1-042b-430a-8c5b-0542f7033a98	locale	user.attribute
c51c3bc1-042b-430a-8c5b-0542f7033a98	true	id.token.claim
c51c3bc1-042b-430a-8c5b-0542f7033a98	true	access.token.claim
c51c3bc1-042b-430a-8c5b-0542f7033a98	locale	claim.name
c51c3bc1-042b-430a-8c5b-0542f7033a98	String	jsonType.label
e8aa29c9-61df-41c6-a516-2a50dd130c10	true	userinfo.token.claim
e8aa29c9-61df-41c6-a516-2a50dd130c10	middleName	user.attribute
e8aa29c9-61df-41c6-a516-2a50dd130c10	true	id.token.claim
e8aa29c9-61df-41c6-a516-2a50dd130c10	true	access.token.claim
e8aa29c9-61df-41c6-a516-2a50dd130c10	middle_name	claim.name
e8aa29c9-61df-41c6-a516-2a50dd130c10	String	jsonType.label
99bd500c-db8d-477c-9d7d-3b0459e0041f	true	userinfo.token.claim
99bd500c-db8d-477c-9d7d-3b0459e0041f	email	user.attribute
99bd500c-db8d-477c-9d7d-3b0459e0041f	true	id.token.claim
99bd500c-db8d-477c-9d7d-3b0459e0041f	true	access.token.claim
99bd500c-db8d-477c-9d7d-3b0459e0041f	email	claim.name
99bd500c-db8d-477c-9d7d-3b0459e0041f	String	jsonType.label
b1879cb5-59fe-4267-ace2-9bb16033bce7	true	userinfo.token.claim
b1879cb5-59fe-4267-ace2-9bb16033bce7	emailVerified	user.attribute
b1879cb5-59fe-4267-ace2-9bb16033bce7	true	id.token.claim
b1879cb5-59fe-4267-ace2-9bb16033bce7	true	access.token.claim
b1879cb5-59fe-4267-ace2-9bb16033bce7	email_verified	claim.name
b1879cb5-59fe-4267-ace2-9bb16033bce7	boolean	jsonType.label
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	formatted	user.attribute.formatted
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	country	user.attribute.country
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	postal_code	user.attribute.postal_code
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	true	userinfo.token.claim
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	street	user.attribute.street
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	true	id.token.claim
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	region	user.attribute.region
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	true	access.token.claim
b0855027-e12b-40a2-9c10-bcf44d8cb6ac	locality	user.attribute.locality
983425fc-0582-48cb-a74f-3d84c4b58586	true	userinfo.token.claim
983425fc-0582-48cb-a74f-3d84c4b58586	phoneNumberVerified	user.attribute
983425fc-0582-48cb-a74f-3d84c4b58586	true	id.token.claim
983425fc-0582-48cb-a74f-3d84c4b58586	true	access.token.claim
983425fc-0582-48cb-a74f-3d84c4b58586	phone_number_verified	claim.name
983425fc-0582-48cb-a74f-3d84c4b58586	boolean	jsonType.label
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	true	userinfo.token.claim
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	phoneNumber	user.attribute
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	true	id.token.claim
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	true	access.token.claim
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	phone_number	claim.name
c793f7a9-bf0c-48d7-a4b6-99102f5af5a4	String	jsonType.label
0168cd70-f7a1-4406-b2de-15c9b11bb80b	true	multivalued
0168cd70-f7a1-4406-b2de-15c9b11bb80b	foo	user.attribute
0168cd70-f7a1-4406-b2de-15c9b11bb80b	true	access.token.claim
0168cd70-f7a1-4406-b2de-15c9b11bb80b	realm_access.roles	claim.name
0168cd70-f7a1-4406-b2de-15c9b11bb80b	String	jsonType.label
b9270ced-976e-45b6-9dac-147a84f28914	true	multivalued
b9270ced-976e-45b6-9dac-147a84f28914	foo	user.attribute
b9270ced-976e-45b6-9dac-147a84f28914	true	access.token.claim
b9270ced-976e-45b6-9dac-147a84f28914	resource_access.${client_id}.roles	claim.name
b9270ced-976e-45b6-9dac-147a84f28914	String	jsonType.label
a20df460-17fa-436e-835f-ca46ef7e5058	true	userinfo.token.claim
a20df460-17fa-436e-835f-ca46ef7e5058	username	user.attribute
a20df460-17fa-436e-835f-ca46ef7e5058	true	id.token.claim
a20df460-17fa-436e-835f-ca46ef7e5058	true	access.token.claim
a20df460-17fa-436e-835f-ca46ef7e5058	upn	claim.name
a20df460-17fa-436e-835f-ca46ef7e5058	String	jsonType.label
c01bc375-b5f9-4936-8251-7c7be8a94b04	true	multivalued
c01bc375-b5f9-4936-8251-7c7be8a94b04	foo	user.attribute
c01bc375-b5f9-4936-8251-7c7be8a94b04	true	id.token.claim
c01bc375-b5f9-4936-8251-7c7be8a94b04	true	access.token.claim
c01bc375-b5f9-4936-8251-7c7be8a94b04	groups	claim.name
c01bc375-b5f9-4936-8251-7c7be8a94b04	String	jsonType.label
4258a352-b86a-4c06-91eb-51e3c06330fe	true	id.token.claim
4258a352-b86a-4c06-91eb-51e3c06330fe	true	access.token.claim
8f898d62-602a-4868-a30c-a583fc40b5f1	true	userinfo.token.claim
8f898d62-602a-4868-a30c-a583fc40b5f1	locale	user.attribute
8f898d62-602a-4868-a30c-a583fc40b5f1	true	id.token.claim
8f898d62-602a-4868-a30c-a583fc40b5f1	true	access.token.claim
8f898d62-602a-4868-a30c-a583fc40b5f1	locale	claim.name
8f898d62-602a-4868-a30c-a583fc40b5f1	String	jsonType.label
\.


--
-- Data for Name: realm; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm (id, access_code_lifespan, user_action_lifespan, access_token_lifespan, account_theme, admin_theme, email_theme, enabled, events_enabled, events_expiration, login_theme, name, not_before, password_policy, registration_allowed, remember_me, reset_password_allowed, social, ssl_required, sso_idle_timeout, sso_max_lifespan, update_profile_on_soc_login, verify_email, master_admin_client, login_lifespan, internationalization_enabled, default_locale, reg_email_as_username, admin_events_enabled, admin_events_details_enabled, edit_username_allowed, otp_policy_counter, otp_policy_window, otp_policy_period, otp_policy_digits, otp_policy_alg, otp_policy_type, browser_flow, registration_flow, direct_grant_flow, reset_credentials_flow, client_auth_flow, offline_session_idle_timeout, revoke_refresh_token, access_token_life_implicit, login_with_email_allowed, duplicate_emails_allowed, docker_auth_flow, refresh_token_max_reuse, allow_user_managed_access, sso_max_lifespan_remember_me, sso_idle_timeout_remember_me, default_role) FROM stdin;
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	60	300	60	\N	\N	\N	t	f	0	\N	master	0	\N	f	f	f	f	EXTERNAL	1800	36000	f	f	7054aec7-dafe-46ea-b752-855f1626b97a	1800	f	\N	f	f	f	f	0	1	30	6	HmacSHA1	totp	261ee39e-ad77-4d9d-8e56-15ec77ea611b	071c0a54-e2e9-4791-bb7e-72853915e371	b31ebba6-89c4-4d34-bd26-18f958560753	0b110242-a5a9-40bd-8ac7-78fec175f3b8	ecb294d1-bb2c-458b-96e6-257a74ee42de	2592000	f	900	t	f	b55b3700-7400-4d72-ab70-ca291b03af2c	0	f	0	0	9248d8ff-8fdf-483f-911c-b400a4715be0
192c7eba-98c5-4d87-9f5f-059ac8515a9f	60	300	300	\N	\N	\N	t	f	0	\N	logprep	0	\N	f	f	f	f	EXTERNAL	1800	36000	f	f	4528294a-48c5-4295-ba48-015c67ad0632	1800	f	\N	f	f	f	f	0	1	30	6	HmacSHA1	totp	655f64bb-8cbd-47fa-b9be-6e4a1ed839ff	519e4a95-50cf-47d1-acde-02dd118e38b0	7b8d49df-024a-4b85-81f0-069c60e8709a	fe832423-ee2e-4105-ad54-2172427ec038	74053835-0f48-4577-843f-ed24711091f7	2592000	f	900	t	f	f1004845-6e8d-4138-9b1e-d98774accaf2	0	f	0	0	355d504e-2e39-4d69-b225-04074afc8263
\.


--
-- Data for Name: realm_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_attribute (name, realm_id, value) FROM stdin;
\.


--
-- Data for Name: realm_default_groups; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_default_groups (realm_id, group_id) FROM stdin;
\.


--
-- Data for Name: realm_enabled_event_types; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_enabled_event_types (realm_id, value) FROM stdin;
\.


--
-- Data for Name: realm_events_listeners; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_events_listeners (realm_id, value) FROM stdin;
ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	jboss-logging
192c7eba-98c5-4d87-9f5f-059ac8515a9f	jboss-logging
\.


--
-- Data for Name: realm_localizations; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_localizations (realm_id, locale, texts) FROM stdin;
\.


--
-- Data for Name: realm_required_credential; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_required_credential (type, form_label, input, secret, realm_id) FROM stdin;
password	password	t	t	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff
password	password	t	t	192c7eba-98c5-4d87-9f5f-059ac8515a9f
\.


--
-- Data for Name: realm_smtp_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_smtp_config (realm_id, value, name) FROM stdin;
\.


--
-- Data for Name: realm_supported_locales; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.realm_supported_locales (realm_id, value) FROM stdin;
\.


--
-- Data for Name: redirect_uris; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.redirect_uris (client_id, value) FROM stdin;
aa04ecbf-e4d0-49ce-a733-ffc6e4309498	/realms/master/account/*
b42513aa-047e-4187-9fd7-7ce4137e3206	/realms/master/account/*
ffa621f0-3e6c-477d-86da-eb2186eb1f40	/admin/master/console/*
713208be-0b29-4727-abc0-1c5102bf0c0e	/realms/logprep/account/*
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	/realms/logprep/account/*
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	/admin/logprep/console/*
05b15c96-ddea-483c-9cd2-0c16d86aefac	/*
02d1898e-b586-4795-b3ff-fd2bae926af0	*
\.


--
-- Data for Name: required_action_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.required_action_config (required_action_id, value, name) FROM stdin;
\.


--
-- Data for Name: required_action_provider; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.required_action_provider (id, alias, name, realm_id, enabled, default_action, provider_id, priority) FROM stdin;
4d1b3a99-c2e1-4848-92e0-d1f98e958898	VERIFY_EMAIL	Verify Email	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	VERIFY_EMAIL	50
f5bcd2bd-d4f4-48eb-af23-a2c3bccd4b08	UPDATE_PROFILE	Update Profile	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	UPDATE_PROFILE	40
4756198c-7435-4f26-9916-cbf3da1ff837	CONFIGURE_TOTP	Configure OTP	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	CONFIGURE_TOTP	10
992c050b-d40e-4a66-ba4e-157151117e87	UPDATE_PASSWORD	Update Password	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	UPDATE_PASSWORD	30
89f1813b-cfab-416c-8cdc-d73e480460b8	TERMS_AND_CONDITIONS	Terms and Conditions	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	f	TERMS_AND_CONDITIONS	20
7836597d-8b07-4888-b75a-3dc563444454	delete_account	Delete Account	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	f	f	delete_account	60
071e9c50-7815-433e-8cf5-5acfc9de298a	update_user_locale	Update User Locale	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	update_user_locale	1000
6c1f802e-6df6-4bc0-a681-e3fbe392f765	webauthn-register	Webauthn Register	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	webauthn-register	70
adbb180c-54a0-49e0-8bca-ec5bcc99703d	webauthn-register-passwordless	Webauthn Register Passwordless	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	t	f	webauthn-register-passwordless	80
14de66fd-31b4-41a6-9185-67c8ba4ee360	VERIFY_EMAIL	Verify Email	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	VERIFY_EMAIL	50
f7434b16-2ff4-4fbc-a256-bec6a32d2c53	UPDATE_PROFILE	Update Profile	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	UPDATE_PROFILE	40
9c37b991-f7aa-442a-8bdf-04e734c2c973	CONFIGURE_TOTP	Configure OTP	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	CONFIGURE_TOTP	10
ec79f935-2d00-4a84-b231-9883d2ba0481	UPDATE_PASSWORD	Update Password	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	UPDATE_PASSWORD	30
a507cfd9-5f8d-4d75-99a6-7d0f9ac2e82c	TERMS_AND_CONDITIONS	Terms and Conditions	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f	f	TERMS_AND_CONDITIONS	20
f01fda74-0b93-4298-b5d4-517366cded0d	delete_account	Delete Account	192c7eba-98c5-4d87-9f5f-059ac8515a9f	f	f	delete_account	60
5b4d9fb3-808e-450c-9787-6b479f5f9f77	update_user_locale	Update User Locale	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	update_user_locale	1000
2b00cacb-77a1-4e2c-8f73-ce3f73972675	webauthn-register	Webauthn Register	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	webauthn-register	70
effef27d-3079-46cd-b53b-8f18d436b228	webauthn-register-passwordless	Webauthn Register Passwordless	192c7eba-98c5-4d87-9f5f-059ac8515a9f	t	f	webauthn-register-passwordless	80
\.


--
-- Data for Name: resource_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_attribute (id, name, value, resource_id) FROM stdin;
\.


--
-- Data for Name: resource_policy; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_policy (resource_id, policy_id) FROM stdin;
\.


--
-- Data for Name: resource_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_scope (resource_id, scope_id) FROM stdin;
\.


--
-- Data for Name: resource_server; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_server (id, allow_rs_remote_mgmt, policy_enforce_mode, decision_strategy) FROM stdin;
\.


--
-- Data for Name: resource_server_perm_ticket; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_server_perm_ticket (id, owner, requester, created_timestamp, granted_timestamp, resource_id, scope_id, resource_server_id, policy_id) FROM stdin;
\.


--
-- Data for Name: resource_server_policy; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_server_policy (id, name, description, type, decision_strategy, logic, resource_server_id, owner) FROM stdin;
\.


--
-- Data for Name: resource_server_resource; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_server_resource (id, name, type, icon_uri, owner, resource_server_id, owner_managed_access, display_name) FROM stdin;
\.


--
-- Data for Name: resource_server_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_server_scope (id, name, icon_uri, resource_server_id, display_name) FROM stdin;
\.


--
-- Data for Name: resource_uris; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.resource_uris (resource_id, value) FROM stdin;
\.


--
-- Data for Name: role_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.role_attribute (id, role_id, name, value) FROM stdin;
\.


--
-- Data for Name: scope_mapping; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.scope_mapping (client_id, role_id) FROM stdin;
b42513aa-047e-4187-9fd7-7ce4137e3206	90bca2e3-0ed3-4f76-8f67-2bf563be2472
b42513aa-047e-4187-9fd7-7ce4137e3206	407b7326-22e9-47de-b32c-f34bdbb48bf6
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	320155b6-942b-4ab0-ae10-20d67b187b7a
89b2e0d2-5fb6-4bfb-82d0-c368080d2663	0c0d6eb7-a699-4100-82b3-f0d6b94cfb10
\.


--
-- Data for Name: scope_policy; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.scope_policy (scope_id, policy_id) FROM stdin;
\.


--
-- Data for Name: user_attribute; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_attribute (name, value, user_id, id) FROM stdin;
\.


--
-- Data for Name: user_consent; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_consent (id, client_id, user_id, created_date, last_updated_date, client_storage_provider, external_client_id) FROM stdin;
\.


--
-- Data for Name: user_consent_client_scope; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_consent_client_scope (user_consent_id, scope_id) FROM stdin;
\.


--
-- Data for Name: user_entity; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_entity (id, email, email_constraint, email_verified, enabled, federation_link, first_name, last_name, realm_id, username, created_timestamp, service_account_client_link, not_before) FROM stdin;
74847ce5-bd87-4a81-93bb-9a838c80a99e	\N	56da2f5a-d1e9-4cf8-85b0-a6d2e1f4dab9	f	t	\N	\N	\N	ccf97ff2-0fd1-472a-8041-b05bbe3ab0ff	admin	1700126430705	\N	0
773ef3df-7d55-4e68-a09e-e40c664adc67	\N	0bf86e2c-a5dd-4786-bfb8-d19ed39f9cd1	f	t	\N	\N	\N	192c7eba-98c5-4d87-9f5f-059ac8515a9f	logprep	1700126495564	\N	0
\.


--
-- Data for Name: user_federation_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_federation_config (user_federation_provider_id, value, name) FROM stdin;
\.


--
-- Data for Name: user_federation_mapper; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_federation_mapper (id, name, federation_provider_id, federation_mapper_type, realm_id) FROM stdin;
\.


--
-- Data for Name: user_federation_mapper_config; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_federation_mapper_config (user_federation_mapper_id, value, name) FROM stdin;
\.


--
-- Data for Name: user_federation_provider; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_federation_provider (id, changed_sync_period, display_name, full_sync_period, last_sync, priority, provider_name, realm_id) FROM stdin;
\.


--
-- Data for Name: user_group_membership; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_group_membership (group_id, user_id) FROM stdin;
\.


--
-- Data for Name: user_required_action; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_required_action (user_id, required_action) FROM stdin;
\.


--
-- Data for Name: user_role_mapping; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_role_mapping (role_id, user_id) FROM stdin;
9248d8ff-8fdf-483f-911c-b400a4715be0	74847ce5-bd87-4a81-93bb-9a838c80a99e
db244a85-417d-4a00-a896-e9312fe77119	74847ce5-bd87-4a81-93bb-9a838c80a99e
dd1dc591-25eb-41b0-ad9b-6626f578f3f9	74847ce5-bd87-4a81-93bb-9a838c80a99e
ef70fd57-bb4d-433d-87ce-b207be534105	74847ce5-bd87-4a81-93bb-9a838c80a99e
223a8341-34d4-4c4d-be7f-105ec6730c6d	74847ce5-bd87-4a81-93bb-9a838c80a99e
8eb82050-5e5c-4a00-b1f7-92a64f1bd403	74847ce5-bd87-4a81-93bb-9a838c80a99e
a2c38582-004b-4821-92cf-c9aced935469	74847ce5-bd87-4a81-93bb-9a838c80a99e
4b283bf4-f313-447b-bd3d-fc2c612fc7bd	74847ce5-bd87-4a81-93bb-9a838c80a99e
433a40d5-9dbe-4114-ba89-187ef4a67b68	74847ce5-bd87-4a81-93bb-9a838c80a99e
85379951-fff1-4821-8184-d027116bffb5	74847ce5-bd87-4a81-93bb-9a838c80a99e
b571f6a9-717c-4cf0-baed-e07c558d5976	74847ce5-bd87-4a81-93bb-9a838c80a99e
2e33949b-0165-455a-a342-71062e369bb0	74847ce5-bd87-4a81-93bb-9a838c80a99e
527489de-7576-4991-a629-3fb0c5604255	74847ce5-bd87-4a81-93bb-9a838c80a99e
febfa69b-d5f3-4c43-9274-081338c35dba	74847ce5-bd87-4a81-93bb-9a838c80a99e
14e594eb-c427-49c1-8201-593c2d6cbe17	74847ce5-bd87-4a81-93bb-9a838c80a99e
f64ea7a4-7f40-4516-a3ce-f388fe482394	74847ce5-bd87-4a81-93bb-9a838c80a99e
abd4c968-9e27-47cf-80ab-0e4e0af854f9	74847ce5-bd87-4a81-93bb-9a838c80a99e
164141e7-7f8e-41a4-a464-c13711bdc55a	74847ce5-bd87-4a81-93bb-9a838c80a99e
ad01d462-d24f-40af-a80b-46688d4100e6	74847ce5-bd87-4a81-93bb-9a838c80a99e
355d504e-2e39-4d69-b225-04074afc8263	773ef3df-7d55-4e68-a09e-e40c664adc67
c580e950-e410-4bf8-a94a-c42c3193c4f1	773ef3df-7d55-4e68-a09e-e40c664adc67
\.


--
-- Data for Name: user_session; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_session (id, auth_method, ip_address, last_session_refresh, login_username, realm_id, remember_me, started, user_id, user_session_state, broker_session_id, broker_user_id) FROM stdin;
\.


--
-- Data for Name: user_session_note; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.user_session_note (user_session, name, value) FROM stdin;
\.


--
-- Data for Name: username_login_failure; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.username_login_failure (realm_id, username, failed_login_not_before, last_failure, last_ip_failure, num_failures) FROM stdin;
\.


--
-- Data for Name: web_origins; Type: TABLE DATA; Schema: public; Owner: keycloak
--

COPY public.web_origins (client_id, value) FROM stdin;
ffa621f0-3e6c-477d-86da-eb2186eb1f40	+
6a67af5f-f536-4211-8f84-d0fcd5c0bccf	+
05b15c96-ddea-483c-9cd2-0c16d86aefac	/*
02d1898e-b586-4795-b3ff-fd2bae926af0	*
\.


--
-- Name: username_login_failure CONSTRAINT_17-2; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.username_login_failure
    ADD CONSTRAINT "CONSTRAINT_17-2" PRIMARY KEY (realm_id, username);


--
-- Name: keycloak_role UK_J3RWUVD56ONTGSUHOGM184WW2-2; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.keycloak_role
    ADD CONSTRAINT "UK_J3RWUVD56ONTGSUHOGM184WW2-2" UNIQUE (name, client_realm_constraint);


--
-- Name: client_auth_flow_bindings c_cli_flow_bind; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_auth_flow_bindings
    ADD CONSTRAINT c_cli_flow_bind PRIMARY KEY (client_id, binding_name);


--
-- Name: client_scope_client c_cli_scope_bind; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope_client
    ADD CONSTRAINT c_cli_scope_bind PRIMARY KEY (client_id, scope_id);


--
-- Name: client_initial_access cnstr_client_init_acc_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_initial_access
    ADD CONSTRAINT cnstr_client_init_acc_pk PRIMARY KEY (id);


--
-- Name: realm_default_groups con_group_id_def_groups; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_default_groups
    ADD CONSTRAINT con_group_id_def_groups UNIQUE (group_id);


--
-- Name: broker_link constr_broker_link_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.broker_link
    ADD CONSTRAINT constr_broker_link_pk PRIMARY KEY (identity_provider, user_id);


--
-- Name: client_user_session_note constr_cl_usr_ses_note; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_user_session_note
    ADD CONSTRAINT constr_cl_usr_ses_note PRIMARY KEY (client_session, name);


--
-- Name: component_config constr_component_config_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.component_config
    ADD CONSTRAINT constr_component_config_pk PRIMARY KEY (id);


--
-- Name: component constr_component_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.component
    ADD CONSTRAINT constr_component_pk PRIMARY KEY (id);


--
-- Name: fed_user_required_action constr_fed_required_action; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_required_action
    ADD CONSTRAINT constr_fed_required_action PRIMARY KEY (required_action, user_id);


--
-- Name: fed_user_attribute constr_fed_user_attr_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_attribute
    ADD CONSTRAINT constr_fed_user_attr_pk PRIMARY KEY (id);


--
-- Name: fed_user_consent constr_fed_user_consent_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_consent
    ADD CONSTRAINT constr_fed_user_consent_pk PRIMARY KEY (id);


--
-- Name: fed_user_credential constr_fed_user_cred_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_credential
    ADD CONSTRAINT constr_fed_user_cred_pk PRIMARY KEY (id);


--
-- Name: fed_user_group_membership constr_fed_user_group; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_group_membership
    ADD CONSTRAINT constr_fed_user_group PRIMARY KEY (group_id, user_id);


--
-- Name: fed_user_role_mapping constr_fed_user_role; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_role_mapping
    ADD CONSTRAINT constr_fed_user_role PRIMARY KEY (role_id, user_id);


--
-- Name: federated_user constr_federated_user; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.federated_user
    ADD CONSTRAINT constr_federated_user PRIMARY KEY (id);


--
-- Name: realm_default_groups constr_realm_default_groups; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_default_groups
    ADD CONSTRAINT constr_realm_default_groups PRIMARY KEY (realm_id, group_id);


--
-- Name: realm_enabled_event_types constr_realm_enabl_event_types; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_enabled_event_types
    ADD CONSTRAINT constr_realm_enabl_event_types PRIMARY KEY (realm_id, value);


--
-- Name: realm_events_listeners constr_realm_events_listeners; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_events_listeners
    ADD CONSTRAINT constr_realm_events_listeners PRIMARY KEY (realm_id, value);


--
-- Name: realm_supported_locales constr_realm_supported_locales; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_supported_locales
    ADD CONSTRAINT constr_realm_supported_locales PRIMARY KEY (realm_id, value);


--
-- Name: identity_provider constraint_2b; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider
    ADD CONSTRAINT constraint_2b PRIMARY KEY (internal_id);


--
-- Name: client_attributes constraint_3c; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_attributes
    ADD CONSTRAINT constraint_3c PRIMARY KEY (client_id, name);


--
-- Name: event_entity constraint_4; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.event_entity
    ADD CONSTRAINT constraint_4 PRIMARY KEY (id);


--
-- Name: federated_identity constraint_40; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.federated_identity
    ADD CONSTRAINT constraint_40 PRIMARY KEY (identity_provider, user_id);


--
-- Name: realm constraint_4a; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm
    ADD CONSTRAINT constraint_4a PRIMARY KEY (id);


--
-- Name: client_session_role constraint_5; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_role
    ADD CONSTRAINT constraint_5 PRIMARY KEY (client_session, role_id);


--
-- Name: user_session constraint_57; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_session
    ADD CONSTRAINT constraint_57 PRIMARY KEY (id);


--
-- Name: user_federation_provider constraint_5c; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_provider
    ADD CONSTRAINT constraint_5c PRIMARY KEY (id);


--
-- Name: client_session_note constraint_5e; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_note
    ADD CONSTRAINT constraint_5e PRIMARY KEY (client_session, name);


--
-- Name: client constraint_7; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT constraint_7 PRIMARY KEY (id);


--
-- Name: client_session constraint_8; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session
    ADD CONSTRAINT constraint_8 PRIMARY KEY (id);


--
-- Name: scope_mapping constraint_81; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.scope_mapping
    ADD CONSTRAINT constraint_81 PRIMARY KEY (client_id, role_id);


--
-- Name: client_node_registrations constraint_84; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_node_registrations
    ADD CONSTRAINT constraint_84 PRIMARY KEY (client_id, name);


--
-- Name: realm_attribute constraint_9; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_attribute
    ADD CONSTRAINT constraint_9 PRIMARY KEY (name, realm_id);


--
-- Name: realm_required_credential constraint_92; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_required_credential
    ADD CONSTRAINT constraint_92 PRIMARY KEY (realm_id, type);


--
-- Name: keycloak_role constraint_a; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.keycloak_role
    ADD CONSTRAINT constraint_a PRIMARY KEY (id);


--
-- Name: admin_event_entity constraint_admin_event_entity; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.admin_event_entity
    ADD CONSTRAINT constraint_admin_event_entity PRIMARY KEY (id);


--
-- Name: authenticator_config_entry constraint_auth_cfg_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authenticator_config_entry
    ADD CONSTRAINT constraint_auth_cfg_pk PRIMARY KEY (authenticator_id, name);


--
-- Name: authentication_execution constraint_auth_exec_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authentication_execution
    ADD CONSTRAINT constraint_auth_exec_pk PRIMARY KEY (id);


--
-- Name: authentication_flow constraint_auth_flow_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authentication_flow
    ADD CONSTRAINT constraint_auth_flow_pk PRIMARY KEY (id);


--
-- Name: authenticator_config constraint_auth_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authenticator_config
    ADD CONSTRAINT constraint_auth_pk PRIMARY KEY (id);


--
-- Name: client_session_auth_status constraint_auth_status_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_auth_status
    ADD CONSTRAINT constraint_auth_status_pk PRIMARY KEY (client_session, authenticator);


--
-- Name: user_role_mapping constraint_c; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_role_mapping
    ADD CONSTRAINT constraint_c PRIMARY KEY (role_id, user_id);


--
-- Name: composite_role constraint_composite_role; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.composite_role
    ADD CONSTRAINT constraint_composite_role PRIMARY KEY (composite, child_role);


--
-- Name: client_session_prot_mapper constraint_cs_pmp_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_prot_mapper
    ADD CONSTRAINT constraint_cs_pmp_pk PRIMARY KEY (client_session, protocol_mapper_id);


--
-- Name: identity_provider_config constraint_d; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider_config
    ADD CONSTRAINT constraint_d PRIMARY KEY (identity_provider_id, name);


--
-- Name: policy_config constraint_dpc; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.policy_config
    ADD CONSTRAINT constraint_dpc PRIMARY KEY (policy_id, name);


--
-- Name: realm_smtp_config constraint_e; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_smtp_config
    ADD CONSTRAINT constraint_e PRIMARY KEY (realm_id, name);


--
-- Name: credential constraint_f; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.credential
    ADD CONSTRAINT constraint_f PRIMARY KEY (id);


--
-- Name: user_federation_config constraint_f9; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_config
    ADD CONSTRAINT constraint_f9 PRIMARY KEY (user_federation_provider_id, name);


--
-- Name: resource_server_perm_ticket constraint_fapmt; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT constraint_fapmt PRIMARY KEY (id);


--
-- Name: resource_server_resource constraint_farsr; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_resource
    ADD CONSTRAINT constraint_farsr PRIMARY KEY (id);


--
-- Name: resource_server_policy constraint_farsrp; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_policy
    ADD CONSTRAINT constraint_farsrp PRIMARY KEY (id);


--
-- Name: associated_policy constraint_farsrpap; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.associated_policy
    ADD CONSTRAINT constraint_farsrpap PRIMARY KEY (policy_id, associated_policy_id);


--
-- Name: resource_policy constraint_farsrpp; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_policy
    ADD CONSTRAINT constraint_farsrpp PRIMARY KEY (resource_id, policy_id);


--
-- Name: resource_server_scope constraint_farsrs; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_scope
    ADD CONSTRAINT constraint_farsrs PRIMARY KEY (id);


--
-- Name: resource_scope constraint_farsrsp; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_scope
    ADD CONSTRAINT constraint_farsrsp PRIMARY KEY (resource_id, scope_id);


--
-- Name: scope_policy constraint_farsrsps; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.scope_policy
    ADD CONSTRAINT constraint_farsrsps PRIMARY KEY (scope_id, policy_id);


--
-- Name: user_entity constraint_fb; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_entity
    ADD CONSTRAINT constraint_fb PRIMARY KEY (id);


--
-- Name: user_federation_mapper_config constraint_fedmapper_cfg_pm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_mapper_config
    ADD CONSTRAINT constraint_fedmapper_cfg_pm PRIMARY KEY (user_federation_mapper_id, name);


--
-- Name: user_federation_mapper constraint_fedmapperpm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_mapper
    ADD CONSTRAINT constraint_fedmapperpm PRIMARY KEY (id);


--
-- Name: fed_user_consent_cl_scope constraint_fgrntcsnt_clsc_pm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.fed_user_consent_cl_scope
    ADD CONSTRAINT constraint_fgrntcsnt_clsc_pm PRIMARY KEY (user_consent_id, scope_id);


--
-- Name: user_consent_client_scope constraint_grntcsnt_clsc_pm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_consent_client_scope
    ADD CONSTRAINT constraint_grntcsnt_clsc_pm PRIMARY KEY (user_consent_id, scope_id);


--
-- Name: user_consent constraint_grntcsnt_pm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_consent
    ADD CONSTRAINT constraint_grntcsnt_pm PRIMARY KEY (id);


--
-- Name: keycloak_group constraint_group; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.keycloak_group
    ADD CONSTRAINT constraint_group PRIMARY KEY (id);


--
-- Name: group_attribute constraint_group_attribute_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.group_attribute
    ADD CONSTRAINT constraint_group_attribute_pk PRIMARY KEY (id);


--
-- Name: group_role_mapping constraint_group_role; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.group_role_mapping
    ADD CONSTRAINT constraint_group_role PRIMARY KEY (role_id, group_id);


--
-- Name: identity_provider_mapper constraint_idpm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider_mapper
    ADD CONSTRAINT constraint_idpm PRIMARY KEY (id);


--
-- Name: idp_mapper_config constraint_idpmconfig; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.idp_mapper_config
    ADD CONSTRAINT constraint_idpmconfig PRIMARY KEY (idp_mapper_id, name);


--
-- Name: migration_model constraint_migmod; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.migration_model
    ADD CONSTRAINT constraint_migmod PRIMARY KEY (id);


--
-- Name: offline_client_session constraint_offl_cl_ses_pk3; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.offline_client_session
    ADD CONSTRAINT constraint_offl_cl_ses_pk3 PRIMARY KEY (user_session_id, client_id, client_storage_provider, external_client_id, offline_flag);


--
-- Name: offline_user_session constraint_offl_us_ses_pk2; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.offline_user_session
    ADD CONSTRAINT constraint_offl_us_ses_pk2 PRIMARY KEY (user_session_id, offline_flag);


--
-- Name: protocol_mapper constraint_pcm; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.protocol_mapper
    ADD CONSTRAINT constraint_pcm PRIMARY KEY (id);


--
-- Name: protocol_mapper_config constraint_pmconfig; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.protocol_mapper_config
    ADD CONSTRAINT constraint_pmconfig PRIMARY KEY (protocol_mapper_id, name);


--
-- Name: redirect_uris constraint_redirect_uris; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.redirect_uris
    ADD CONSTRAINT constraint_redirect_uris PRIMARY KEY (client_id, value);


--
-- Name: required_action_config constraint_req_act_cfg_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.required_action_config
    ADD CONSTRAINT constraint_req_act_cfg_pk PRIMARY KEY (required_action_id, name);


--
-- Name: required_action_provider constraint_req_act_prv_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.required_action_provider
    ADD CONSTRAINT constraint_req_act_prv_pk PRIMARY KEY (id);


--
-- Name: user_required_action constraint_required_action; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_required_action
    ADD CONSTRAINT constraint_required_action PRIMARY KEY (required_action, user_id);


--
-- Name: resource_uris constraint_resour_uris_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_uris
    ADD CONSTRAINT constraint_resour_uris_pk PRIMARY KEY (resource_id, value);


--
-- Name: role_attribute constraint_role_attribute_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.role_attribute
    ADD CONSTRAINT constraint_role_attribute_pk PRIMARY KEY (id);


--
-- Name: user_attribute constraint_user_attribute_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_attribute
    ADD CONSTRAINT constraint_user_attribute_pk PRIMARY KEY (id);


--
-- Name: user_group_membership constraint_user_group; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_group_membership
    ADD CONSTRAINT constraint_user_group PRIMARY KEY (group_id, user_id);


--
-- Name: user_session_note constraint_usn_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_session_note
    ADD CONSTRAINT constraint_usn_pk PRIMARY KEY (user_session, name);


--
-- Name: web_origins constraint_web_origins; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.web_origins
    ADD CONSTRAINT constraint_web_origins PRIMARY KEY (client_id, value);


--
-- Name: databasechangeloglock databasechangeloglock_pkey; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.databasechangeloglock
    ADD CONSTRAINT databasechangeloglock_pkey PRIMARY KEY (id);


--
-- Name: client_scope_attributes pk_cl_tmpl_attr; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope_attributes
    ADD CONSTRAINT pk_cl_tmpl_attr PRIMARY KEY (scope_id, name);


--
-- Name: client_scope pk_cli_template; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope
    ADD CONSTRAINT pk_cli_template PRIMARY KEY (id);


--
-- Name: resource_server pk_resource_server; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server
    ADD CONSTRAINT pk_resource_server PRIMARY KEY (id);


--
-- Name: client_scope_role_mapping pk_template_scope; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope_role_mapping
    ADD CONSTRAINT pk_template_scope PRIMARY KEY (scope_id, role_id);


--
-- Name: default_client_scope r_def_cli_scope_bind; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.default_client_scope
    ADD CONSTRAINT r_def_cli_scope_bind PRIMARY KEY (realm_id, scope_id);


--
-- Name: realm_localizations realm_localizations_pkey; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_localizations
    ADD CONSTRAINT realm_localizations_pkey PRIMARY KEY (realm_id, locale);


--
-- Name: resource_attribute res_attr_pk; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_attribute
    ADD CONSTRAINT res_attr_pk PRIMARY KEY (id);


--
-- Name: keycloak_group sibling_names; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.keycloak_group
    ADD CONSTRAINT sibling_names UNIQUE (realm_id, parent_group, name);


--
-- Name: identity_provider uk_2daelwnibji49avxsrtuf6xj33; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider
    ADD CONSTRAINT uk_2daelwnibji49avxsrtuf6xj33 UNIQUE (provider_alias, realm_id);


--
-- Name: client uk_b71cjlbenv945rb6gcon438at; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client
    ADD CONSTRAINT uk_b71cjlbenv945rb6gcon438at UNIQUE (realm_id, client_id);


--
-- Name: client_scope uk_cli_scope; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope
    ADD CONSTRAINT uk_cli_scope UNIQUE (realm_id, name);


--
-- Name: user_entity uk_dykn684sl8up1crfei6eckhd7; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_entity
    ADD CONSTRAINT uk_dykn684sl8up1crfei6eckhd7 UNIQUE (realm_id, email_constraint);


--
-- Name: resource_server_resource uk_frsr6t700s9v50bu18ws5ha6; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_resource
    ADD CONSTRAINT uk_frsr6t700s9v50bu18ws5ha6 UNIQUE (name, owner, resource_server_id);


--
-- Name: resource_server_perm_ticket uk_frsr6t700s9v50bu18ws5pmt; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT uk_frsr6t700s9v50bu18ws5pmt UNIQUE (owner, requester, resource_server_id, resource_id, scope_id);


--
-- Name: resource_server_policy uk_frsrpt700s9v50bu18ws5ha6; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_policy
    ADD CONSTRAINT uk_frsrpt700s9v50bu18ws5ha6 UNIQUE (name, resource_server_id);


--
-- Name: resource_server_scope uk_frsrst700s9v50bu18ws5ha6; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_scope
    ADD CONSTRAINT uk_frsrst700s9v50bu18ws5ha6 UNIQUE (name, resource_server_id);


--
-- Name: user_consent uk_jkuwuvd56ontgsuhogm8uewrt; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_consent
    ADD CONSTRAINT uk_jkuwuvd56ontgsuhogm8uewrt UNIQUE (client_id, client_storage_provider, external_client_id, user_id);


--
-- Name: realm uk_orvsdmla56612eaefiq6wl5oi; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm
    ADD CONSTRAINT uk_orvsdmla56612eaefiq6wl5oi UNIQUE (name);


--
-- Name: user_entity uk_ru8tt6t700s9v50bu18ws5ha6; Type: CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_entity
    ADD CONSTRAINT uk_ru8tt6t700s9v50bu18ws5ha6 UNIQUE (realm_id, username);


--
-- Name: idx_admin_event_time; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_admin_event_time ON public.admin_event_entity USING btree (realm_id, admin_event_time);


--
-- Name: idx_assoc_pol_assoc_pol_id; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_assoc_pol_assoc_pol_id ON public.associated_policy USING btree (associated_policy_id);


--
-- Name: idx_auth_config_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_auth_config_realm ON public.authenticator_config USING btree (realm_id);


--
-- Name: idx_auth_exec_flow; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_auth_exec_flow ON public.authentication_execution USING btree (flow_id);


--
-- Name: idx_auth_exec_realm_flow; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_auth_exec_realm_flow ON public.authentication_execution USING btree (realm_id, flow_id);


--
-- Name: idx_auth_flow_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_auth_flow_realm ON public.authentication_flow USING btree (realm_id);


--
-- Name: idx_cl_clscope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_cl_clscope ON public.client_scope_client USING btree (scope_id);


--
-- Name: idx_client_id; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_client_id ON public.client USING btree (client_id);


--
-- Name: idx_client_init_acc_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_client_init_acc_realm ON public.client_initial_access USING btree (realm_id);


--
-- Name: idx_client_session_session; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_client_session_session ON public.client_session USING btree (session_id);


--
-- Name: idx_clscope_attrs; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_clscope_attrs ON public.client_scope_attributes USING btree (scope_id);


--
-- Name: idx_clscope_cl; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_clscope_cl ON public.client_scope_client USING btree (client_id);


--
-- Name: idx_clscope_protmap; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_clscope_protmap ON public.protocol_mapper USING btree (client_scope_id);


--
-- Name: idx_clscope_role; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_clscope_role ON public.client_scope_role_mapping USING btree (scope_id);


--
-- Name: idx_compo_config_compo; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_compo_config_compo ON public.component_config USING btree (component_id);


--
-- Name: idx_component_provider_type; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_component_provider_type ON public.component USING btree (provider_type);


--
-- Name: idx_component_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_component_realm ON public.component USING btree (realm_id);


--
-- Name: idx_composite; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_composite ON public.composite_role USING btree (composite);


--
-- Name: idx_composite_child; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_composite_child ON public.composite_role USING btree (child_role);


--
-- Name: idx_defcls_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_defcls_realm ON public.default_client_scope USING btree (realm_id);


--
-- Name: idx_defcls_scope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_defcls_scope ON public.default_client_scope USING btree (scope_id);


--
-- Name: idx_event_time; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_event_time ON public.event_entity USING btree (realm_id, event_time);


--
-- Name: idx_fedidentity_feduser; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fedidentity_feduser ON public.federated_identity USING btree (federated_user_id);


--
-- Name: idx_fedidentity_user; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fedidentity_user ON public.federated_identity USING btree (user_id);


--
-- Name: idx_fu_attribute; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_attribute ON public.fed_user_attribute USING btree (user_id, realm_id, name);


--
-- Name: idx_fu_cnsnt_ext; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_cnsnt_ext ON public.fed_user_consent USING btree (user_id, client_storage_provider, external_client_id);


--
-- Name: idx_fu_consent; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_consent ON public.fed_user_consent USING btree (user_id, client_id);


--
-- Name: idx_fu_consent_ru; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_consent_ru ON public.fed_user_consent USING btree (realm_id, user_id);


--
-- Name: idx_fu_credential; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_credential ON public.fed_user_credential USING btree (user_id, type);


--
-- Name: idx_fu_credential_ru; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_credential_ru ON public.fed_user_credential USING btree (realm_id, user_id);


--
-- Name: idx_fu_group_membership; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_group_membership ON public.fed_user_group_membership USING btree (user_id, group_id);


--
-- Name: idx_fu_group_membership_ru; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_group_membership_ru ON public.fed_user_group_membership USING btree (realm_id, user_id);


--
-- Name: idx_fu_required_action; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_required_action ON public.fed_user_required_action USING btree (user_id, required_action);


--
-- Name: idx_fu_required_action_ru; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_required_action_ru ON public.fed_user_required_action USING btree (realm_id, user_id);


--
-- Name: idx_fu_role_mapping; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_role_mapping ON public.fed_user_role_mapping USING btree (user_id, role_id);


--
-- Name: idx_fu_role_mapping_ru; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_fu_role_mapping_ru ON public.fed_user_role_mapping USING btree (realm_id, user_id);


--
-- Name: idx_group_att_by_name_value; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_group_att_by_name_value ON public.group_attribute USING btree (name, ((value)::character varying(250)));


--
-- Name: idx_group_attr_group; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_group_attr_group ON public.group_attribute USING btree (group_id);


--
-- Name: idx_group_role_mapp_group; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_group_role_mapp_group ON public.group_role_mapping USING btree (group_id);


--
-- Name: idx_id_prov_mapp_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_id_prov_mapp_realm ON public.identity_provider_mapper USING btree (realm_id);


--
-- Name: idx_ident_prov_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_ident_prov_realm ON public.identity_provider USING btree (realm_id);


--
-- Name: idx_keycloak_role_client; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_keycloak_role_client ON public.keycloak_role USING btree (client);


--
-- Name: idx_keycloak_role_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_keycloak_role_realm ON public.keycloak_role USING btree (realm);


--
-- Name: idx_offline_css_preload; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_offline_css_preload ON public.offline_client_session USING btree (client_id, offline_flag);


--
-- Name: idx_offline_uss_by_user; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_offline_uss_by_user ON public.offline_user_session USING btree (user_id, realm_id, offline_flag);


--
-- Name: idx_offline_uss_by_usersess; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_offline_uss_by_usersess ON public.offline_user_session USING btree (realm_id, offline_flag, user_session_id);


--
-- Name: idx_offline_uss_createdon; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_offline_uss_createdon ON public.offline_user_session USING btree (created_on);


--
-- Name: idx_offline_uss_preload; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_offline_uss_preload ON public.offline_user_session USING btree (offline_flag, created_on, user_session_id);


--
-- Name: idx_protocol_mapper_client; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_protocol_mapper_client ON public.protocol_mapper USING btree (client_id);


--
-- Name: idx_realm_attr_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_attr_realm ON public.realm_attribute USING btree (realm_id);


--
-- Name: idx_realm_clscope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_clscope ON public.client_scope USING btree (realm_id);


--
-- Name: idx_realm_def_grp_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_def_grp_realm ON public.realm_default_groups USING btree (realm_id);


--
-- Name: idx_realm_evt_list_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_evt_list_realm ON public.realm_events_listeners USING btree (realm_id);


--
-- Name: idx_realm_evt_types_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_evt_types_realm ON public.realm_enabled_event_types USING btree (realm_id);


--
-- Name: idx_realm_master_adm_cli; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_master_adm_cli ON public.realm USING btree (master_admin_client);


--
-- Name: idx_realm_supp_local_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_realm_supp_local_realm ON public.realm_supported_locales USING btree (realm_id);


--
-- Name: idx_redir_uri_client; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_redir_uri_client ON public.redirect_uris USING btree (client_id);


--
-- Name: idx_req_act_prov_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_req_act_prov_realm ON public.required_action_provider USING btree (realm_id);


--
-- Name: idx_res_policy_policy; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_res_policy_policy ON public.resource_policy USING btree (policy_id);


--
-- Name: idx_res_scope_scope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_res_scope_scope ON public.resource_scope USING btree (scope_id);


--
-- Name: idx_res_serv_pol_res_serv; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_res_serv_pol_res_serv ON public.resource_server_policy USING btree (resource_server_id);


--
-- Name: idx_res_srv_res_res_srv; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_res_srv_res_res_srv ON public.resource_server_resource USING btree (resource_server_id);


--
-- Name: idx_res_srv_scope_res_srv; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_res_srv_scope_res_srv ON public.resource_server_scope USING btree (resource_server_id);


--
-- Name: idx_role_attribute; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_role_attribute ON public.role_attribute USING btree (role_id);


--
-- Name: idx_role_clscope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_role_clscope ON public.client_scope_role_mapping USING btree (role_id);


--
-- Name: idx_scope_mapping_role; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_scope_mapping_role ON public.scope_mapping USING btree (role_id);


--
-- Name: idx_scope_policy_policy; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_scope_policy_policy ON public.scope_policy USING btree (policy_id);


--
-- Name: idx_update_time; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_update_time ON public.migration_model USING btree (update_time);


--
-- Name: idx_us_sess_id_on_cl_sess; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_us_sess_id_on_cl_sess ON public.offline_client_session USING btree (user_session_id);


--
-- Name: idx_usconsent_clscope; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_usconsent_clscope ON public.user_consent_client_scope USING btree (user_consent_id);


--
-- Name: idx_user_attribute; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_attribute ON public.user_attribute USING btree (user_id);


--
-- Name: idx_user_attribute_name; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_attribute_name ON public.user_attribute USING btree (name, value);


--
-- Name: idx_user_consent; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_consent ON public.user_consent USING btree (user_id);


--
-- Name: idx_user_credential; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_credential ON public.credential USING btree (user_id);


--
-- Name: idx_user_email; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_email ON public.user_entity USING btree (email);


--
-- Name: idx_user_group_mapping; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_group_mapping ON public.user_group_membership USING btree (user_id);


--
-- Name: idx_user_reqactions; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_reqactions ON public.user_required_action USING btree (user_id);


--
-- Name: idx_user_role_mapping; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_role_mapping ON public.user_role_mapping USING btree (user_id);


--
-- Name: idx_user_service_account; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_user_service_account ON public.user_entity USING btree (realm_id, service_account_client_link);


--
-- Name: idx_usr_fed_map_fed_prv; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_usr_fed_map_fed_prv ON public.user_federation_mapper USING btree (federation_provider_id);


--
-- Name: idx_usr_fed_map_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_usr_fed_map_realm ON public.user_federation_mapper USING btree (realm_id);


--
-- Name: idx_usr_fed_prv_realm; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_usr_fed_prv_realm ON public.user_federation_provider USING btree (realm_id);


--
-- Name: idx_web_orig_client; Type: INDEX; Schema: public; Owner: keycloak
--

CREATE INDEX idx_web_orig_client ON public.web_origins USING btree (client_id);


--
-- Name: client_session_auth_status auth_status_constraint; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_auth_status
    ADD CONSTRAINT auth_status_constraint FOREIGN KEY (client_session) REFERENCES public.client_session(id);


--
-- Name: identity_provider fk2b4ebc52ae5c3b34; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider
    ADD CONSTRAINT fk2b4ebc52ae5c3b34 FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: client_attributes fk3c47c64beacca966; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_attributes
    ADD CONSTRAINT fk3c47c64beacca966 FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: federated_identity fk404288b92ef007a6; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.federated_identity
    ADD CONSTRAINT fk404288b92ef007a6 FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: client_node_registrations fk4129723ba992f594; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_node_registrations
    ADD CONSTRAINT fk4129723ba992f594 FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: client_session_note fk5edfb00ff51c2736; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_note
    ADD CONSTRAINT fk5edfb00ff51c2736 FOREIGN KEY (client_session) REFERENCES public.client_session(id);


--
-- Name: user_session_note fk5edfb00ff51d3472; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_session_note
    ADD CONSTRAINT fk5edfb00ff51d3472 FOREIGN KEY (user_session) REFERENCES public.user_session(id);


--
-- Name: client_session_role fk_11b7sgqw18i532811v7o2dv76; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_role
    ADD CONSTRAINT fk_11b7sgqw18i532811v7o2dv76 FOREIGN KEY (client_session) REFERENCES public.client_session(id);


--
-- Name: redirect_uris fk_1burs8pb4ouj97h5wuppahv9f; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.redirect_uris
    ADD CONSTRAINT fk_1burs8pb4ouj97h5wuppahv9f FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: user_federation_provider fk_1fj32f6ptolw2qy60cd8n01e8; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_provider
    ADD CONSTRAINT fk_1fj32f6ptolw2qy60cd8n01e8 FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: client_session_prot_mapper fk_33a8sgqw18i532811v7o2dk89; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session_prot_mapper
    ADD CONSTRAINT fk_33a8sgqw18i532811v7o2dk89 FOREIGN KEY (client_session) REFERENCES public.client_session(id);


--
-- Name: realm_required_credential fk_5hg65lybevavkqfki3kponh9v; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_required_credential
    ADD CONSTRAINT fk_5hg65lybevavkqfki3kponh9v FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: resource_attribute fk_5hrm2vlf9ql5fu022kqepovbr; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_attribute
    ADD CONSTRAINT fk_5hrm2vlf9ql5fu022kqepovbr FOREIGN KEY (resource_id) REFERENCES public.resource_server_resource(id);


--
-- Name: user_attribute fk_5hrm2vlf9ql5fu043kqepovbr; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_attribute
    ADD CONSTRAINT fk_5hrm2vlf9ql5fu043kqepovbr FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: user_required_action fk_6qj3w1jw9cvafhe19bwsiuvmd; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_required_action
    ADD CONSTRAINT fk_6qj3w1jw9cvafhe19bwsiuvmd FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: keycloak_role fk_6vyqfe4cn4wlq8r6kt5vdsj5c; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.keycloak_role
    ADD CONSTRAINT fk_6vyqfe4cn4wlq8r6kt5vdsj5c FOREIGN KEY (realm) REFERENCES public.realm(id);


--
-- Name: realm_smtp_config fk_70ej8xdxgxd0b9hh6180irr0o; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_smtp_config
    ADD CONSTRAINT fk_70ej8xdxgxd0b9hh6180irr0o FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: realm_attribute fk_8shxd6l3e9atqukacxgpffptw; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_attribute
    ADD CONSTRAINT fk_8shxd6l3e9atqukacxgpffptw FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: composite_role fk_a63wvekftu8jo1pnj81e7mce2; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.composite_role
    ADD CONSTRAINT fk_a63wvekftu8jo1pnj81e7mce2 FOREIGN KEY (composite) REFERENCES public.keycloak_role(id);


--
-- Name: authentication_execution fk_auth_exec_flow; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authentication_execution
    ADD CONSTRAINT fk_auth_exec_flow FOREIGN KEY (flow_id) REFERENCES public.authentication_flow(id);


--
-- Name: authentication_execution fk_auth_exec_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authentication_execution
    ADD CONSTRAINT fk_auth_exec_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: authentication_flow fk_auth_flow_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authentication_flow
    ADD CONSTRAINT fk_auth_flow_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: authenticator_config fk_auth_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.authenticator_config
    ADD CONSTRAINT fk_auth_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: client_session fk_b4ao2vcvat6ukau74wbwtfqo1; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_session
    ADD CONSTRAINT fk_b4ao2vcvat6ukau74wbwtfqo1 FOREIGN KEY (session_id) REFERENCES public.user_session(id);


--
-- Name: user_role_mapping fk_c4fqv34p1mbylloxang7b1q3l; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_role_mapping
    ADD CONSTRAINT fk_c4fqv34p1mbylloxang7b1q3l FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: client_scope_attributes fk_cl_scope_attr_scope; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope_attributes
    ADD CONSTRAINT fk_cl_scope_attr_scope FOREIGN KEY (scope_id) REFERENCES public.client_scope(id);


--
-- Name: client_scope_role_mapping fk_cl_scope_rm_scope; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_scope_role_mapping
    ADD CONSTRAINT fk_cl_scope_rm_scope FOREIGN KEY (scope_id) REFERENCES public.client_scope(id);


--
-- Name: client_user_session_note fk_cl_usr_ses_note; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_user_session_note
    ADD CONSTRAINT fk_cl_usr_ses_note FOREIGN KEY (client_session) REFERENCES public.client_session(id);


--
-- Name: protocol_mapper fk_cli_scope_mapper; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.protocol_mapper
    ADD CONSTRAINT fk_cli_scope_mapper FOREIGN KEY (client_scope_id) REFERENCES public.client_scope(id);


--
-- Name: client_initial_access fk_client_init_acc_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.client_initial_access
    ADD CONSTRAINT fk_client_init_acc_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: component_config fk_component_config; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.component_config
    ADD CONSTRAINT fk_component_config FOREIGN KEY (component_id) REFERENCES public.component(id);


--
-- Name: component fk_component_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.component
    ADD CONSTRAINT fk_component_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: realm_default_groups fk_def_groups_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_default_groups
    ADD CONSTRAINT fk_def_groups_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: user_federation_mapper_config fk_fedmapper_cfg; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_mapper_config
    ADD CONSTRAINT fk_fedmapper_cfg FOREIGN KEY (user_federation_mapper_id) REFERENCES public.user_federation_mapper(id);


--
-- Name: user_federation_mapper fk_fedmapperpm_fedprv; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_mapper
    ADD CONSTRAINT fk_fedmapperpm_fedprv FOREIGN KEY (federation_provider_id) REFERENCES public.user_federation_provider(id);


--
-- Name: user_federation_mapper fk_fedmapperpm_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_mapper
    ADD CONSTRAINT fk_fedmapperpm_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: associated_policy fk_frsr5s213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.associated_policy
    ADD CONSTRAINT fk_frsr5s213xcx4wnkog82ssrfy FOREIGN KEY (associated_policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: scope_policy fk_frsrasp13xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.scope_policy
    ADD CONSTRAINT fk_frsrasp13xcx4wnkog82ssrfy FOREIGN KEY (policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: resource_server_perm_ticket fk_frsrho213xcx4wnkog82sspmt; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT fk_frsrho213xcx4wnkog82sspmt FOREIGN KEY (resource_server_id) REFERENCES public.resource_server(id);


--
-- Name: resource_server_resource fk_frsrho213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_resource
    ADD CONSTRAINT fk_frsrho213xcx4wnkog82ssrfy FOREIGN KEY (resource_server_id) REFERENCES public.resource_server(id);


--
-- Name: resource_server_perm_ticket fk_frsrho213xcx4wnkog83sspmt; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT fk_frsrho213xcx4wnkog83sspmt FOREIGN KEY (resource_id) REFERENCES public.resource_server_resource(id);


--
-- Name: resource_server_perm_ticket fk_frsrho213xcx4wnkog84sspmt; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT fk_frsrho213xcx4wnkog84sspmt FOREIGN KEY (scope_id) REFERENCES public.resource_server_scope(id);


--
-- Name: associated_policy fk_frsrpas14xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.associated_policy
    ADD CONSTRAINT fk_frsrpas14xcx4wnkog82ssrfy FOREIGN KEY (policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: scope_policy fk_frsrpass3xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.scope_policy
    ADD CONSTRAINT fk_frsrpass3xcx4wnkog82ssrfy FOREIGN KEY (scope_id) REFERENCES public.resource_server_scope(id);


--
-- Name: resource_server_perm_ticket fk_frsrpo2128cx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_perm_ticket
    ADD CONSTRAINT fk_frsrpo2128cx4wnkog82ssrfy FOREIGN KEY (policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: resource_server_policy fk_frsrpo213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_policy
    ADD CONSTRAINT fk_frsrpo213xcx4wnkog82ssrfy FOREIGN KEY (resource_server_id) REFERENCES public.resource_server(id);


--
-- Name: resource_scope fk_frsrpos13xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_scope
    ADD CONSTRAINT fk_frsrpos13xcx4wnkog82ssrfy FOREIGN KEY (resource_id) REFERENCES public.resource_server_resource(id);


--
-- Name: resource_policy fk_frsrpos53xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_policy
    ADD CONSTRAINT fk_frsrpos53xcx4wnkog82ssrfy FOREIGN KEY (resource_id) REFERENCES public.resource_server_resource(id);


--
-- Name: resource_policy fk_frsrpp213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_policy
    ADD CONSTRAINT fk_frsrpp213xcx4wnkog82ssrfy FOREIGN KEY (policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: resource_scope fk_frsrps213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_scope
    ADD CONSTRAINT fk_frsrps213xcx4wnkog82ssrfy FOREIGN KEY (scope_id) REFERENCES public.resource_server_scope(id);


--
-- Name: resource_server_scope fk_frsrso213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_server_scope
    ADD CONSTRAINT fk_frsrso213xcx4wnkog82ssrfy FOREIGN KEY (resource_server_id) REFERENCES public.resource_server(id);


--
-- Name: composite_role fk_gr7thllb9lu8q4vqa4524jjy8; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.composite_role
    ADD CONSTRAINT fk_gr7thllb9lu8q4vqa4524jjy8 FOREIGN KEY (child_role) REFERENCES public.keycloak_role(id);


--
-- Name: user_consent_client_scope fk_grntcsnt_clsc_usc; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_consent_client_scope
    ADD CONSTRAINT fk_grntcsnt_clsc_usc FOREIGN KEY (user_consent_id) REFERENCES public.user_consent(id);


--
-- Name: user_consent fk_grntcsnt_user; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_consent
    ADD CONSTRAINT fk_grntcsnt_user FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: group_attribute fk_group_attribute_group; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.group_attribute
    ADD CONSTRAINT fk_group_attribute_group FOREIGN KEY (group_id) REFERENCES public.keycloak_group(id);


--
-- Name: group_role_mapping fk_group_role_group; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.group_role_mapping
    ADD CONSTRAINT fk_group_role_group FOREIGN KEY (group_id) REFERENCES public.keycloak_group(id);


--
-- Name: realm_enabled_event_types fk_h846o4h0w8epx5nwedrf5y69j; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_enabled_event_types
    ADD CONSTRAINT fk_h846o4h0w8epx5nwedrf5y69j FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: realm_events_listeners fk_h846o4h0w8epx5nxev9f5y69j; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_events_listeners
    ADD CONSTRAINT fk_h846o4h0w8epx5nxev9f5y69j FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: identity_provider_mapper fk_idpm_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider_mapper
    ADD CONSTRAINT fk_idpm_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: idp_mapper_config fk_idpmconfig; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.idp_mapper_config
    ADD CONSTRAINT fk_idpmconfig FOREIGN KEY (idp_mapper_id) REFERENCES public.identity_provider_mapper(id);


--
-- Name: web_origins fk_lojpho213xcx4wnkog82ssrfy; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.web_origins
    ADD CONSTRAINT fk_lojpho213xcx4wnkog82ssrfy FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: scope_mapping fk_ouse064plmlr732lxjcn1q5f1; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.scope_mapping
    ADD CONSTRAINT fk_ouse064plmlr732lxjcn1q5f1 FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: protocol_mapper fk_pcm_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.protocol_mapper
    ADD CONSTRAINT fk_pcm_realm FOREIGN KEY (client_id) REFERENCES public.client(id);


--
-- Name: credential fk_pfyr0glasqyl0dei3kl69r6v0; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.credential
    ADD CONSTRAINT fk_pfyr0glasqyl0dei3kl69r6v0 FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: protocol_mapper_config fk_pmconfig; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.protocol_mapper_config
    ADD CONSTRAINT fk_pmconfig FOREIGN KEY (protocol_mapper_id) REFERENCES public.protocol_mapper(id);


--
-- Name: default_client_scope fk_r_def_cli_scope_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.default_client_scope
    ADD CONSTRAINT fk_r_def_cli_scope_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: required_action_provider fk_req_act_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.required_action_provider
    ADD CONSTRAINT fk_req_act_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: resource_uris fk_resource_server_uris; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.resource_uris
    ADD CONSTRAINT fk_resource_server_uris FOREIGN KEY (resource_id) REFERENCES public.resource_server_resource(id);


--
-- Name: role_attribute fk_role_attribute_id; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.role_attribute
    ADD CONSTRAINT fk_role_attribute_id FOREIGN KEY (role_id) REFERENCES public.keycloak_role(id);


--
-- Name: realm_supported_locales fk_supported_locales_realm; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.realm_supported_locales
    ADD CONSTRAINT fk_supported_locales_realm FOREIGN KEY (realm_id) REFERENCES public.realm(id);


--
-- Name: user_federation_config fk_t13hpu1j94r2ebpekr39x5eu5; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_federation_config
    ADD CONSTRAINT fk_t13hpu1j94r2ebpekr39x5eu5 FOREIGN KEY (user_federation_provider_id) REFERENCES public.user_federation_provider(id);


--
-- Name: user_group_membership fk_user_group_user; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.user_group_membership
    ADD CONSTRAINT fk_user_group_user FOREIGN KEY (user_id) REFERENCES public.user_entity(id);


--
-- Name: policy_config fkdc34197cf864c4e43; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.policy_config
    ADD CONSTRAINT fkdc34197cf864c4e43 FOREIGN KEY (policy_id) REFERENCES public.resource_server_policy(id);


--
-- Name: identity_provider_config fkdc4897cf864c4e43; Type: FK CONSTRAINT; Schema: public; Owner: keycloak
--

ALTER TABLE ONLY public.identity_provider_config
    ADD CONSTRAINT fkdc4897cf864c4e43 FOREIGN KEY (identity_provider_id) REFERENCES public.identity_provider(internal_id);


--
-- PostgreSQL database dump complete
--

