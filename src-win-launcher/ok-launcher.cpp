#include <iostream>
#include <windows.h>
#include <fstream>
#include <string>
#include <regex>
#include <codecvt>
#include <vector>
#include <sstream>
#include <shlwapi.h> // Required for PathRemoveFileSpecW

#pragma comment(lib, "shlwapi.lib") // Link against Shlwapi.lib
#pragma comment(linker, "/SUBSYSTEM:WINDOWS")
#pragma comment(linker, "/ENTRY:mainCRTStartup")

std::wstring getAbsolutePath(const std::wstring& relativePath) {
    wchar_t fullPath[MAX_PATH];
    if (_wfullpath(fullPath, relativePath.c_str(), MAX_PATH) != NULL) {
        return std::wstring(fullPath);
    }
    else {
        MessageBoxW(NULL, L"Failed to get absolute path", L"Error", MB_OK);
        return relativePath; // Return the original path if conversion fails
    }
}


std::string WideStringToUTF8(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    std::wstring_convert<std::codecvt_utf8<wchar_t>> conv;
    return conv.to_bytes(wstr);
}

std::wstring UTF8ToWideString(const std::string& str) {
    if (str.empty()) return std::wstring();
    std::wstring_convert<std::codecvt_utf8<wchar_t>> conv;
    return conv.from_bytes(str);
}

bool modifyVenvCfg(const std::wstring& envDir, const std::wstring& relativPythonDir) {
    std::wstring absEnvDir = getAbsolutePath(envDir);
    std::wstring pythonDir = getAbsolutePath(relativPythonDir);
    std::wstring filePath = absEnvDir + L"\\pyvenv.cfg";

    // Open the file in UTF-8 mode
    std::ifstream file(filePath, std::ios::in | std::ios::binary);
    if (!file.is_open()) {
        return false;
    }

    std::ostringstream contentStream;
    contentStream << file.rdbuf();
    std::string contentUTF8 = contentStream.str();
    file.close();

    std::wstring content = UTF8ToWideString(contentUTF8);

    // Modify the content using regex
    std::wregex homeRegex(LR"((\s*home\s*=\s*).*)");
    std::wregex executableRegex(LR"((\s*executable\s*=\s*).*)");
    std::wregex commandRegex(LR"((\s*command\s*=\s*).*)");

    content = std::regex_replace(content, homeRegex, L"$1" + pythonDir);
    content = std::regex_replace(content, executableRegex, L"$1" + pythonDir + L"\\python.exe");
    content = std::regex_replace(content, commandRegex, L"$1" + pythonDir + L"\\python.exe -m venv " + absEnvDir);

    // Convert the modified wide string back to UTF-8
    std::string contentModifiedUTF8 = WideStringToUTF8(content);

    // Compare the original and modified content
    if (contentUTF8 != contentModifiedUTF8) {
        // Write the modified content back to the file in UTF-8
        std::ofstream outFile(filePath, std::ios::out | std::ios::binary);
        if (!outFile.is_open()) {
            //MessageBoxW(NULL, L"Failed to open pyvenv.cfg file for writing", L"Error", MB_OK);
            return false;
        }

        outFile.write(contentModifiedUTF8.c_str(), contentModifiedUTF8.size());
        outFile.close();
    }
    return true;
}

std::wstring readAppVersion(const std::wstring& filePath) {
    std::wifstream file(filePath);
    if (!file.is_open()) {
        //MessageBoxW(NULL, L"Failed to open JSON file", L"Error", MB_OK);
        return L"0.0.1"; // Default version if file read fails
    }

    std::wstring content((std::istreambuf_iterator<wchar_t>(file)), std::istreambuf_iterator<wchar_t>());
    file.close();

    std::wregex versionRegex(LR"(\"app_version\"\s*:\s*"([^"]+)\")");
    std::wsmatch match;
    if (std::regex_search(content, match, versionRegex)) {
        return match[1].str();
    }
    else {
        MessageBoxW(NULL, L"Failed to find launcher_version in JSON file", L"Error", MB_OK);
        return L"0.0.1"; // Default version if regex search fails
    }
}


// Helper to display error messages
void ShowError(const std::wstring& title, const std::wstring& message) {
    MessageBoxW(NULL, message.c_str(), title.c_str(), MB_OK | MB_ICONERROR);
}
// Gets the directory containing the executable
std::wstring GetExecutableDirectory() {
    WCHAR exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    PathRemoveFileSpecW(exePath);
    return std::wstring(exePath);
}
// Sets up environment variables for the Python process
void SetupPythonEnvironment() {
    SetEnvironmentVariableW(L"PYTHONHOME", NULL);
    SetEnvironmentVariableW(L"PYTHONPATH", NULL);
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");
    SetEnvironmentVariableW(L"PYTHONUNBUFFERED", L"1"); // Force unbuffered output
}
// Determines the command to launch the Python script
std::wstring DeterminePythonCommand(const std::wstring& appVersion, int argc, char* argv[]) {
    std::wstring command;
    std::wstring baseRepoPath = L".\\repo\\" + appVersion;
    std::wstring versionedVenvPath = baseRepoPath + L"\\.venv";
    std::wstring versionedMainScript = baseRepoPath + L"\\main.py";
    std::wstring localVenvPython = L".\\.venv\\Scripts\\python.exe";
    std::wstring localMainScript = L"main.py";
    // Try versioned path first
    if (modifyVenvCfg(versionedVenvPath, L".\\python\\")) { // Assuming modifyVenvCfg checks venv existence too
        command = versionedVenvPath + L"\\Scripts\\python.exe " + versionedMainScript;
    }
    else {
        // Try local venv path
        if (GetFileAttributesW(localVenvPython.c_str()) != INVALID_FILE_ATTRIBUTES) {
            command = localVenvPython + L" " + localMainScript;
        }
        else {
            ShowError(L"Error", L"Failed to find Python environment.");
            return L""; // Return empty string on failure
        }
    }
    // Append command line arguments
    std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>> converter;
    for (int i = 1; i < argc; ++i) {
        try {
            // Safely convert narrow argv[] to wide string
            std::string narrowArg(argv[i]);
            std::wstring wideArg = converter.from_bytes(narrowArg);
            command += L" \"" + wideArg + L"\"";
        }
        catch (const std::range_error& e) {
            ShowError(L"Argument Error", L"Failed to convert command line argument.");
            // Handle invalid byte sequence if necessary, maybe skip argument
        }
    }
    return command;
}
// Creates a pipe for redirecting IO and configures handles
bool CreateRedirectedPipe(HANDLE& hRead, HANDLE& hWrite) {
    SECURITY_ATTRIBUTES sa = { sizeof(SECURITY_ATTRIBUTES), NULL, TRUE }; // Inheritable handles
    if (!CreatePipe(&hRead, &hWrite, &sa, 0)) {
        ShowError(L"Error", L"Failed to create pipe.");
        return false;
    }
    // Ensure the read handle is NOT inherited by the child process.
    if (!SetHandleInformation(hRead, HANDLE_FLAG_INHERIT, 0)) {
        ShowError(L"Error", L"Failed to set handle information.");
        CloseHandle(hRead);
        CloseHandle(hWrite);
        return false;
    }
    return true;
}
// Configures STARTUPINFO for the child process
void ConfigureStartupInfo(STARTUPINFO& si, HANDLE hStdOutWrite) {
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(STARTUPINFO);
    si.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
    si.wShowWindow = SW_HIDE; // Hide python window
    si.hStdInput = NULL;      // No input redirection
    si.hStdOutput = hStdOutWrite;
    si.hStdError = hStdOutWrite; // Redirect both stdout and stderr
}
// Launches the process and returns true on success
bool LaunchProcess(std::wstring command, STARTUPINFO& si, PROCESS_INFORMATION& pi) {
    ZeroMemory(&pi, sizeof(pi));
    // CREATE_NO_WINDOW prevents console. TRUE = inherit handles.
    if (!CreateProcessW(NULL, &command[0], NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        DWORD dwError = GetLastError();
        std::wstring errorMsg = L"Failed to create process. Error code: " + std::to_wstring(dwError) + L"\nCommand: " + command;
        ShowError(L"Launcher Error", errorMsg);
        return false;
    }
    return true;
}
// Reads all output from the pipe
std::wstring ReadOutputFromPipe(HANDLE hRead) {
    std::vector<CHAR> outputBuffer;
    CHAR buffer[4096];
    DWORD bytesRead;
    while (ReadFile(hRead, buffer, sizeof(buffer), &bytesRead, NULL) && bytesRead > 0) {
        outputBuffer.insert(outputBuffer.end(), buffer, buffer + bytesRead);
    }
    // Convert potentially multi-byte output (like utf-8) to wstring
    if (outputBuffer.empty()) {
        return L"";
    }
    // Use UTF-8 conversion
    std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>> converter;
    try {
        return converter.from_bytes(std::string(outputBuffer.begin(), outputBuffer.end()));
    }
    catch (const std::range_error& e) {
        // Handle potential conversion error if output wasn't valid utf-8
        return L"[Error converting process output]";
    }
}
// Waits for process completion, checks exit code, and handles errors
void HandleProcessResult(PROCESS_INFORMATION& pi, HANDLE hReadPipe) {
    // Wait reasonably long, but not indefinitely
    WaitForSingleObject(pi.hProcess, 1000); // 30 seconds timeout
    DWORD exitCode = STILL_ACTIVE; // Check if it's still running after wait
    GetExitCodeProcess(pi.hProcess, &exitCode);
    std::wstring outputStr = ReadOutputFromPipe(hReadPipe); // Read output regardless of timeout or exit code

    if (exitCode != 0 and exitCode != 259) {
        std::wstring errorMsg = L"Python script failed with exit code: " + std::to_wstring(exitCode) + L"\n\nOutput:\n" + outputStr;
        ShowError(L"Python Script Error", errorMsg);
    }
    // else: Success (exit code 0) - do nothing extra
}

void ChangeCWD() {
    WCHAR exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    PathRemoveFileSpecW(exePath);
    if (!SetCurrentDirectoryW(exePath)) {
        MessageBoxW(NULL, L"Failed to change working directory to EXE location.", L"Error", MB_OK | MB_ICONERROR);
    }
}

int main(int argc, char* argv[]) {
    ChangeCWD();

    std::wstring appVersion = readAppVersion(L".\\configs\\launcher.json"); // Assuming this function exists
    if (appVersion.empty()) {
        ShowError(L"Config Error", L"Could not read app version from .\\configs\\launcher.json");
        return 1;
    }
    std::wstring command = DeterminePythonCommand(appVersion, argc, argv);
    if (command.empty()) {
        return 1; // Error shown in DeterminePythonCommand
    }
    SetupPythonEnvironment();
    HANDLE hStdOutRead = NULL, hStdOutWrite = NULL;
    if (!CreateRedirectedPipe(hStdOutRead, hStdOutWrite)) {
        return 1;
    }
    STARTUPINFO si;
    PROCESS_INFORMATION pi;
    ConfigureStartupInfo(si, hStdOutWrite);
    if (LaunchProcess(command, si, pi)) {
        CloseHandle(hStdOutWrite); // VERY IMPORTANT: Close parent's write handle
        hStdOutWrite = NULL;       // Avoid double close later
        HandleProcessResult(pi, hStdOutRead);
        // Clean up process handles
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    else {
        // Launch failed, error shown in LaunchProcess
        // Still need to close the write handle if pipe creation succeeded
        if (hStdOutWrite) CloseHandle(hStdOutWrite);
    }
    // Always close the read handle
    if (hStdOutRead) CloseHandle(hStdOutRead);
    return 0; // Indicate successful launcher execution (regardless of python script outcome)
}