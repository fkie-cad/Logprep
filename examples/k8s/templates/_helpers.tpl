{{/*
Expand the name of the chart.
*/}}
{{- define "opensiem.name" -}}
{{- printf "%s" .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "opensiem.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "opensiem.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "opensiem.release" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
{{- end }}

{{/*
Common labels
*/}}
{{- define "opensiem.labels" -}}
helm.sh/chart: {{ include "opensiem.chart" . }}
{{ include "opensiem.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/application: {{ include "opensiem.name" . }}
{{- range $key, $value := .Values.extraLabels }}
{{ $key}}: {{ $value | quote }}
{{- end }}
{{- end }}

{{/*
{{- end }}

{{/*
Selector labels
*/}}
{{- define "opensiem.selectorLabels" -}}
app.kubernetes.io/name: {{ include "opensiem.fullname" . }}
app.kubernetes.io/instance: {{ include "opensiem.release" . }}
{{- end }}

{{/*
{{- end }}

{{/*
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "opensiem.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "opensiem.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

