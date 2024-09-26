{{/*
Expand the name of the chart.
*/}}
{{- define "logprep.name" -}}
{{- printf "%s" .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "logprep.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "logprep.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "logprep.release" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
{{- end }}

{{/*
Common labels
*/}}
{{- define "logprep.labels" -}}
helm.sh/chart: {{ include "logprep.chart" . }}
{{ include "logprep.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/application: {{ include "logprep.name" . }}
{{- range $key, $value := .Values.extraLabels }}
{{ $key}}: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
{{- end }}

{{/*
Selector labels
*/}}
{{- define "logprep.selectorLabels" -}}
app.kubernetes.io/name: {{ include "logprep.fullname" . }}
app.kubernetes.io/instance: {{ include "logprep.release" . }}
{{- end }}

{{/*
{{- end }}

{{/*
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "logprep.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "logprep.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

