using System;

public static class GameStateManager
{
    public static event EventHandler<OnStateChangedEventArgs> OnStateChanged;
    public static string PreviousSceneName;
    public static GameState State
    {
        get => _state;
        set
        {
            if (_state == value) return;
            _state = value;
            //Debug.Log(State);
            OnStateChanged?.Invoke(null, new OnStateChangedEventArgs { CurrentState = _state });
        }
    }

    public class OnStateChangedEventArgs : EventArgs
    {
        public GameState CurrentState;
    }


    private static GameState _state;
}

public enum GameState
{
    FirstEntry,
    MainMenu,
    AtHome,
    PhysicsExam,
    MathsExam,
    ITExam,
    ExamsFailed,
    ExamsPassed,
    map,
    lvl1,
    lvl2,
    lvl3,
}
