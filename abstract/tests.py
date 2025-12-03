from rest_framework.test import APITestCase
from .models import A, B, C, A_STATES, B_STATES, C_STATES
from . import process  # Import to ensure process bindings are executed

# TODO: test logs

def create_objs(
        state_a: A_STATES = A_STATES.A0, 
        state_b: B_STATES = B_STATES.B0, 
        state_c: C_STATES = C_STATES.C0,
) -> tuple[A, B, C]:
    c = C.objects.create(name='C', status=state_c)
    c.save()
    b = B.objects.create(name='B', c=c, status=state_b)
    b.save()
    a = A.objects.create(name='A', b=b, status=state_a)
    a.save()
    return a, b, c

class AbstractTests(APITestCase):

    def test_initial_state(self):
        a, b, c = create_objs()
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A0, B_STATES.B0, C_STATES.C0))

    def test_transition_A0_A1(self):
        a, b, c = create_objs()
        a.process.A0_A1()
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A1, B_STATES.B0, C_STATES.C0))

    def test_transition_A0_A2(self):
        a, b, c = create_objs()
        a.process.A0_A2()
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A2, B_STATES.B0, C_STATES.C0))

    def test_transition_A0_A3(self):
        a, b, c = create_objs()
        a.process.A0_A3()
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A3, B_STATES.B2, C_STATES.C0))
        self.assertEqual((a.error_code, b.error_code, c.error_code), (0, 0, 0))
        self.assertTrue(not a.process.state.is_locked())
        self.assertTrue(not b.process.state.is_locked())
        self.assertTrue(not c.process.state.is_locked())

    def test_transition_A0_A3_with_error(self):
        a, b, c = create_objs()
        b.raise_error = True
        b.save(update_fields=['raise_error'])
        a.process.A0_A3()
        # TODO: a should be in A0 state because of the error on B1_B2 transition
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A0, B_STATES.Err, C_STATES.C0))
        self.assertEqual((a.error_code, b.error_code, c.error_code), (0, 1, 0))
        self.assertTrue(not a.process.state.is_locked())
        self.assertTrue(not b.process.state.is_locked())
        self.assertTrue(not c.process.state.is_locked())

    def test_transition_to_A4(self):
        a, b, c = create_objs(A_STATES.A1)
        a.process.to_A4()
        self.assertEqual((a.status, b.status, c.status), (A_STATES.A4, B_STATES.B0, C_STATES.C0))


# TODO: 1. Mark all depricated things
# TODO: 2. Test logs
# TODO: 3. Detect stuck states
