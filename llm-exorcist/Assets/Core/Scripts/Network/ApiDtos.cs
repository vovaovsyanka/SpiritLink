using System;

// Модели запросов и ответов бэкенда (bek-project/app/schemas.py).
// Имена полей совпадают с JSON, поэтому snake_case. Разбираются через JsonUtility.
namespace Core.Scripts.Network
{
    [Serializable]
    public class CredentialsRequest
    {
        public string login;
        public string password;
    }

    [Serializable]
    public class TokenResponse
    {
        public string token;
        public string expires_at;
    }

    [Serializable]
    public class PassState
    {
        public string pass_id;
        public bool started;
        /// <summary>investigation | puzzle | free_prompt | done; пусто, если не начато.</summary>
        public string phase;
        /// <summary>Пройдено хотя бы раз (остаётся true при перепрохождении).</summary>
        public bool completed;
        /// <summary>Найденные подсказки: полный текст карточки (puzzleText).</summary>
        public string[] collected_clues;
        /// <summary>Прочитанные разговоры по порядку, без повторов.</summary>
        public JournalDialogue[] journal;
    }

    [Serializable]
    public class JournalEntry
    {
        public string name;
        public string text;
    }

    [Serializable]
    public class JournalDialogue
    {
        public JournalEntry[] entries;
    }

    [Serializable]
    public class JournalRequest
    {
        public JournalEntry[] entries;
    }

    [Serializable]
    public class ProgressResponse
    {
        public string login;
        public string display_name;
        public int world_level;
        public string current_pass_id;
        public PassState[] passes;
    }

    [Serializable]
    public class ClueRequest
    {
        public string clue;
    }

    [Serializable]
    public class PhaseRequest
    {
        public string phase;
    }

    [Serializable]
    public class WorldLevelInfo
    {
        public int level;
        public string name;
        public bool available;
    }

    [Serializable]
    public class WorldLevelsResponse
    {
        public int current;
        public WorldLevelInfo[] levels;
    }

    [Serializable]
    public class WorldLevelRequest
    {
        public int world_level;
    }

    [Serializable]
    public class PredictRequest
    {
        public string pass_id;
        public string text;
    }

    [Serializable]
    public class PredictResponse
    {
        public string text;
        public bool passed;
    }

    [Serializable]
    public class ErrorResponse
    {
        public string detail;
    }

    [Serializable]
    public class ServerConfigFile
    {
        public string server_url;
    }

    /// <summary>Фазы прохождения — строки ровно как в API.</summary>
    public static class Phases
    {
        public const string Investigation = "investigation";
        public const string Puzzle = "puzzle";
        public const string FreePrompt = "free_prompt";
        public const string Done = "done";
    }
}
