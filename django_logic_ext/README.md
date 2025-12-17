App **django-logic-ext** is experimental improvement of **django-logic** library. It is located inside **gv** 
project, but  it is abstract and could be extracted to separate library.

-----

### Main idea

Main idea is to make processing of transitions stable and reliable.
To achieve this, we use Message Queue pattern with minor modifications to suit our specific needs

### Structure

- **models.TranstionMessage** - model that storing information about transition
- **models.TranstionMessageChannel** - model that storing different channels to use for scalability
- **transitions.MQTransition** - creates TransitionMessage instance from transition
- **handler.TransitionMessageHandler** - fetches TransitionMessage instance from DB, restores transition and runs side effects
- **tasks** - periodically collect messages from db and runs handler
- **signals** - run handler immediately after TransitionMessage instance created

### Transitions processing

1) TransitionMessage instance created during **change_state** method of **MQTransition** class.
2) Signal launches **TransitionMessageHandler** for created message.
3) **TransitionMessageHandler** takes message and runs its side effects.
4) If side effects fail, error saved to message.
4) Periodic task takes incompleted messages and tries to handle them again until errors limit reached.

