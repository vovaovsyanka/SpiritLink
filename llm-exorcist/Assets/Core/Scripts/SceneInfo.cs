using System.Collections.Generic;

public abstract class SceneInfo
{
    public const string MAIN_MENU_SCENE = "MainMenuScene";
    public const string KITOMIR_HOME_SCENE = "KitomirHomeScene";
    public const string CORRIDOR_SCENE = "CorridorScene";
    public const string PHYSICS_AUDITORIUM_SCENE = "PhysicsAuditoriumScene";
    public const string MATHS_AUDITORIUM_SCENE = "MathsAuditoriumScene";
    public const string ITAUDITORIUM_SCENE = "ITAuditoriumScene";
    public const string HAPPY_END_SCENE = "HappyEndScene";
    public const string SAD_END_SCENE = "SadEndScene";
    public const string SECRET_GAME_MODE_SCENE = "SecretGameModeScene";
    public const string MAP_SCENE = "Map";
    public const string LVL1_SCENE = "LVL1";
    public const string LVL2_SCENE = "LVL2";
    public const string LVL3_SCENE = "LVL3";


    public static Dictionary<SceneNames, string> SceneNamesMap = new() {
        { SceneNames.MainMenuScene, "MainMenuScene" },
        { SceneNames.KitomirHomeScene, "KitomirHomeScene" },
        { SceneNames.CorridorScene, "CorridorScene" },
        { SceneNames.PhysicsAuditoriumScene, "PhysicsAuditoriumScene" },
        { SceneNames.MathsAuditoriumScene, "MathsAuditoriumScene" },
        { SceneNames.ItauditoriumScene, "ITAuditoriumScene" },
        { SceneNames.HappyEndScene, "HappyEndScene" },
        { SceneNames.SadEndScene, "SadEndScene" },
        { SceneNames.map, "Map" },
        { SceneNames.lvl1, "LVL1" },
                { SceneNames.lvl2, "LVL2" },
                        { SceneNames.lvl3, "LVL3" },
    };
    
    public static Dictionary<string, GameState> SceneStates = new() {
        { MAIN_MENU_SCENE, GameState.MainMenu },
        { KITOMIR_HOME_SCENE, GameState.AtHome },
        { CORRIDOR_SCENE, GameState.PhysicsExam },
        { PHYSICS_AUDITORIUM_SCENE, GameState.PhysicsExam },
        { MATHS_AUDITORIUM_SCENE, GameState.MathsExam },
        { ITAUDITORIUM_SCENE, GameState.ITExam },
        { SAD_END_SCENE, GameState.ExamsFailed },
        { HAPPY_END_SCENE, GameState.ExamsPassed },
        { SECRET_GAME_MODE_SCENE, GameState.MainMenu },
        { MAP_SCENE, GameState.map },
        { LVL1_SCENE, GameState.lvl1 },
        { LVL2_SCENE, GameState.lvl2 },
        { LVL3_SCENE, GameState.lvl3 },
    };
    
}

public enum SceneNames
{
    MainMenuScene,
    KitomirHomeScene,
    CorridorScene,
    PhysicsAuditoriumScene,
    MathsAuditoriumScene,
    ItauditoriumScene,
    HappyEndScene,
    SadEndScene,
    SecretGameModeScene,
    map,
    lvl1,
    lvl2,
    lvl3
}
