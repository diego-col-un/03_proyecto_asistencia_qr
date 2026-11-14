// Pipeline serverless para el Sistema de asistencia con QR.
// No usa Docker ni EC2: solo valida la plantilla CloudFormation y despliega
// el stack con scripts/deploy.sh (empaqueta las Lambdas y hace cfn deploy).
//
// Credenciales AWS: se inyectan como variables de entorno del agente
// (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN en Learner Lab).
// El despliegue real solo corre en la rama main.
pipeline {
  agent any

  parameters {
    string(name: 'NOMBRE_EQUIPO', defaultValue: 'qr-serverless',
           description: 'Nombre corto del equipo (prefijo de los recursos)')
    string(name: 'SCAN_BASE_URL', defaultValue: '',
           description: 'URL de la pagina del estudiante (opcional, se pasa como ScanBaseUrl)')
  }

  environment {
    AWS_DEFAULT_REGION = 'us-east-1'
  }

  stages {
    stage('Validar IaC') {
      steps {
        sh 'python -m pip install --quiet --upgrade cfn-lint || pip3 install --quiet --upgrade cfn-lint'
        sh 'cfn-lint iac/*.yaml'
      }
    }

    stage('Desplegar') {
      when { branch 'main' }
      steps {
        sh '''
          chmod +x scripts/deploy.sh
          if [ -n "$SCAN_BASE_URL" ]; then
            ./scripts/deploy.sh "$NOMBRE_EQUIPO" "ScanBaseUrl=$SCAN_BASE_URL"
          else
            ./scripts/deploy.sh "$NOMBRE_EQUIPO"
          fi
        '''
      }
    }
  }

  post {
    success { echo 'Pipeline OK (cfn-lint + despliegue serverless).' }
    failure { echo 'Pipeline fallo: revisar validacion de la plantilla o el despliegue.' }
  }
}
