# Copyrights here

# Configuration
$VENV_NAME = "sk_venv"
$REQ_FILE = "requirements.txt"

# Check for Python
Write-Host "Checking for Python installation..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        $python = "py -3"
    } else {
        Write-Error "Python not found. Please install Python 3 and ensure it's in your PATH."
        exit 1
    }
} else {
    $python = "python"
}

# Create virtual environment
if (-not (Test-Path $VENV_NAME)) {
    Write-Host "Creating virtual environment '$VENV_NAME'..."
    & $python -m venv $VENV_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
} else {
    Write-Host "Virtual environment '$VENV_NAME' already exists."
}

# Activate the venv for this session
Write-Host "Activating virtual environment..."
$activateScript = ".\$VENV_NAME\Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Error "Activation script not found at $activateScript"
    exit 1
}

# Execute the activation script in current session
& $activateScript

# Upgrade pip
Write-Host "Upgrading pip..."
pip install --upgrade pip

# Install requirements
if (Test-Path $REQ_FILE) {
    Write-Host "Installing packages from $REQ_FILE "
    pip install -r $REQ_FILE
} else {
    Write-Host "No $REQ_FILE found, skipping package installation."
}

Write-Host "Setup complete!"